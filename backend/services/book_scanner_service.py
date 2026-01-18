"""
书籍扫描服务 - 自动扫描博客库，聚合成教程书籍
"""
import json
import uuid
import logging
import os
from typing import Dict, Any, List, Optional

from services.database_service import DatabaseService
from services.blog_generator.prompts.prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)

# 主题到图标的映射
THEME_ICONS = {
    'ai': '🤖',
    'web': '🌐',
    'data': '📊',
    'devops': '⚙️',
    'security': '🔐',
    'general': '📖'
}


class BookScannerService:
    """书籍扫描服务"""
    
    def __init__(self, db: DatabaseService, llm_client=None):
        """
        初始化书籍扫描服务
        
        Args:
            db: 数据库服务
            llm_client: LLM 客户端（用于智能决策）
        """
        self.db = db
        self.llm = llm_client
    
    def scan_and_update_books(self, force_refresh: bool = True) -> Dict[str, Any]:
        """
        扫描博客库，自动聚合成书籍
        
        Args:
            force_refresh: 是否强制刷新现有书籍大纲（即使没有新博客）
        
        Returns:
            扫描结果统计
        """
        logger.info("开始扫描博客库...")
        
        # 1. 获取未分配的博客
        unassigned_blogs = self.db.get_unassigned_blogs()
        logger.info(f"发现 {len(unassigned_blogs)} 篇未分配的博客")
        
        # 1.1 检查并补充缺失的摘要
        summaries_generated = self._ensure_blog_summaries(unassigned_blogs)
        if summaries_generated > 0:
            logger.info(f"已为 {summaries_generated} 篇博客生成摘要")
        
        # 2. 获取现有书籍
        existing_books = self._get_existing_books_with_details()
        logger.info(f"现有 {len(existing_books)} 本书籍")
        
        # 如果没有未分配的博客，但需要强制刷新现有书籍
        if not unassigned_blogs:
            if force_refresh and existing_books:
                logger.info("没有新博客，但强制刷新现有书籍大纲...")
                books_refreshed = self._refresh_existing_books(existing_books)
                return {
                    "status": "success",
                    "message": f"已刷新 {books_refreshed} 本书籍的大纲",
                    "blogs_processed": 0,
                    "books_created": 0,
                    "books_updated": books_refreshed,
                    "summaries_generated": summaries_generated
                }
            else:
                return {
                    "status": "success",
                    "message": "没有新的博客需要处理",
                    "blogs_processed": 0,
                    "books_created": 0,
                    "books_updated": 0,
                    "summaries_generated": summaries_generated
                }
        
        # 3. 调用 LLM 进行智能决策
        decision = self._llm_decide_assignments(unassigned_blogs, existing_books)
        
        # 4. 应用决策
        result = self._apply_assignments(decision, unassigned_blogs, existing_books)
        result['summaries_generated'] = summaries_generated
        
        logger.info(f"扫描完成: 处理 {result['blogs_processed']} 篇博客, "
                   f"创建 {result['books_created']} 本新书, "
                   f"更新 {result['books_updated']} 本书")
        
        return result
    
    def _refresh_existing_books(self, books: List[Dict[str, Any]]) -> int:
        """
        强制刷新现有书籍的大纲
        
        Args:
            books: 书籍列表
            
        Returns:
            刷新的书籍数量
        """
        count = 0
        for book in books:
            try:
                result = self.rescan_book(book['id'])
                if result.get('status') == 'success':
                    count += 1
                    logger.info(f"刷新书籍大纲: {book['title']}")
            except Exception as e:
                logger.warning(f"刷新书籍大纲失败: {book['id']}, {e}")
        return count
    
    def _ensure_blog_summaries(self, blogs: List[Dict[str, Any]]) -> int:
        """
        确保所有博客都有摘要，如果没有则生成
        
        Args:
            blogs: 博客列表
            
        Returns:
            生成摘要的数量
        """
        if not self.llm:
            return 0
        
        from services.blog_generator.blog_service import extract_article_summary
        
        count = 0
        for blog in blogs:
            # 检查是否已有摘要
            if blog.get('summary'):
                continue
            
            # 生成摘要
            try:
                content = blog.get('markdown_content', '') or ''
                
                summary = extract_article_summary(
                    llm_client=self.llm,
                    title=blog.get('topic', ''),
                    content=content,
                    max_length=500
                )
                
                if summary:
                    self.db.update_history_summary(blog['id'], summary)
                    blog['summary'] = summary  # 更新内存中的数据
                    count += 1
                    logger.info(f"生成博客摘要: {blog['id']} - {blog.get('topic', '')[:30]}")
            except Exception as e:
                logger.warning(f"生成博客摘要失败: {blog['id']}, {e}")
        
        return count
    
    def _get_existing_books_with_details(self) -> List[Dict[str, Any]]:
        """获取现有书籍及其详细信息"""
        books = self.db.list_books(status='active')
        
        for book in books:
            # 获取章节信息
            book['chapters'] = self.db.get_book_chapters(book['id'])
            # 获取关联的博客
            book['related_blogs'] = self.db.get_blogs_by_book(book['id'])
            # 解析大纲
            if book.get('outline'):
                try:
                    book['outline'] = json.loads(book['outline'])
                except json.JSONDecodeError:
                    book['outline'] = None
        
        return books
    
    def _llm_decide_assignments(
        self,
        unassigned_blogs: List[Dict[str, Any]],
        existing_books: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        调用 LLM 决策博客分配
        
        Args:
            unassigned_blogs: 未分配的博客列表
            existing_books: 现有书籍列表
        
        Returns:
            LLM 的决策结果
        """
        if not self.llm:
            logger.warning("LLM 客户端未配置，使用默认分配策略")
            return self._default_assignment_strategy(unassigned_blogs, existing_books)
        
        # 构建 LLM 上下文
        context = self._build_llm_context(unassigned_blogs, existing_books)
        
        # 使用模板渲染 Prompt
        prompt_manager = get_prompt_manager()
        prompt = prompt_manager.render_book_scanner(
            existing_books_info=context['existing_books_info'],
            new_blogs_info=context['new_blogs_info']
        )
        
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}]
            )
            
            # 提取 JSON
            response_text = response if isinstance(response, str) else response.get('content', '')
            
            # 尝试解析 JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                decision = json.loads(json_str)
            else:
                raise json.JSONDecodeError("No JSON found", response_text, 0)
                
        except Exception as e:
            logger.error(f"LLM 决策失败: {e}")
            decision = self._default_assignment_strategy(unassigned_blogs, existing_books)
        
        return decision
    
    def _build_llm_context(
        self,
        unassigned_blogs: List[Dict[str, Any]],
        existing_books: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """构建 LLM 的输入上下文"""
        
        # 现有书籍信息
        books_info = []
        for book in existing_books:
            book_summary = f"""
书籍 ID: {book['id']}
书籍标题: {book['title']}
主题: {book.get('theme', 'general')}
描述: {book.get('description', '无')}
包含博客: {len(book.get('related_blogs', []))} 篇
已有章节: {len(book.get('chapters', []))} 个
大纲:
{json.dumps(book.get('outline'), ensure_ascii=False, indent=2) if book.get('outline') else '无'}
"""
            books_info.append(book_summary)
        
        existing_books_info = "\n---\n".join(books_info) if books_info else "暂无现有书籍"
        
        # 新增博客信息
        blogs_info = []
        for blog in unassigned_blogs:
            content = blog.get('markdown_content', '') or ''
            
            # 优先使用已保存的摘要
            summary = blog.get('summary', '')
            
            # 提取博客大纲章节标题
            outline = blog.get('outline', '')
            outline_summary = ''
            if outline:
                try:
                    outline_data = json.loads(outline) if isinstance(outline, str) else outline
                    sections = outline_data.get('sections', [])
                    outline_summary = '\n'.join([f"  - {s.get('title', '')}" for s in sections[:5]])
                except:
                    pass
            
            # 如果没有摘要，使用内容前 500 字
            if not summary:
                summary = content[:500] if content else ""
            
            blog_entry = f"""
博客 ID: {blog['id']}
标题: {blog.get('topic', '无标题')}
类型: {blog.get('article_type', 'tutorial')}
字数: {len(content)}
章节数: {blog.get('sections_count', 0)}
代码块数: {blog.get('code_blocks_count', 0)}
生成时间: {blog.get('created_at', '')}
大纲:
{outline_summary if outline_summary else '无'}
摘要:
{summary}
"""
            blogs_info.append(blog_entry)
        
        new_blogs_info = "\n---\n".join(blogs_info)
        
        return {
            "existing_books_info": existing_books_info,
            "new_blogs_info": new_blogs_info
        }
    
    def _default_assignment_strategy(
        self,
        unassigned_blogs: List[Dict[str, Any]],
        existing_books: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """默认分配策略（无 LLM 时使用）"""
        
        # 简单策略：为所有未分配博客创建一本新书
        if not unassigned_blogs:
            return {"assignments": [], "new_books": [], "outline_updates": []}
        
        # 创建一本通用书籍
        new_book = {
            "temp_id": "new_book_default",
            "title": "技术博客合集",
            "theme": "general",
            "description": "自动聚合的技术博客文章",
            "outline": {
                "chapters": []
            }
        }
        
        assignments = []
        for idx, blog in enumerate(unassigned_blogs):
            chapter_index = idx + 1
            assignments.append({
                "blog_id": blog['id'],
                "action": "create_new_book",
                "book_id": "new_book_default",
                "chapter_index": chapter_index,
                "chapter_title": blog.get('topic', f'章节 {chapter_index}'),
                "section_index": f"{chapter_index}.1",
                "section_title": blog.get('topic', f'内容 {chapter_index}'),
                "reasoning": "默认分配策略"
            })
            
            new_book["outline"]["chapters"].append({
                "index": chapter_index,
                "title": blog.get('topic', f'章节 {chapter_index}'),
                "sections": [{
                    "index": f"{chapter_index}.1",
                    "title": blog.get('topic', f'内容 {chapter_index}'),
                    "blog_id": blog['id']
                }]
            })
        
        return {
            "assignments": assignments,
            "new_books": [new_book],
            "outline_updates": []
        }
    
    def _apply_assignments(
        self,
        decision: Dict[str, Any],
        unassigned_blogs: List[Dict[str, Any]],
        existing_books: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """应用 LLM 的决策，更新数据库"""
        
        result = {
            "status": "success",
            "blogs_processed": len(unassigned_blogs),
            "books_created": 0,
            "books_updated": 0,
            "new_book_ids": [],
            "updated_book_ids": []
        }
        
        # 1. 创建新书籍
        new_book_mapping = {}  # temp_id -> real_id
        for new_book_info in decision.get('new_books', []):
            book_id = f"book_{uuid.uuid4().hex[:12]}"
            temp_id = new_book_info.get('temp_id', '')
            new_book_mapping[temp_id] = book_id
            
            # 创建书籍
            self.db.create_book(
                book_id,
                new_book_info['title'],
                new_book_info.get('theme', 'general'),
                new_book_info.get('description', '')
            )
            
            # 保存大纲
            outline = new_book_info.get('outline', {})
            self.db.update_book(
                book_id,
                outline=json.dumps(outline, ensure_ascii=False)
            )
            
            result['books_created'] += 1
            result['new_book_ids'].append(book_id)
            logger.info(f"创建新书籍: {book_id} - {new_book_info['title']}")
            
            # 异步生成封面（不阻塞主流程）
            try:
                self.generate_book_cover(book_id)
            except Exception as e:
                logger.warning(f"自动生成封面失败: {book_id}, {e}")
        
        # 2. 处理分配
        book_chapters = {}  # book_id -> [chapters]
        
        for assignment in decision.get('assignments', []):
            blog_id = assignment['blog_id']
            
            # 确定目标书籍 ID（优先从映射中查找，支持 temp_id 转换）
            raw_book_id = assignment.get('book_id', '')
            book_id = new_book_mapping.get(raw_book_id, raw_book_id)
            
            if not book_id:
                logger.warning(f"博客 {blog_id} 无法分配：缺少 book_id")
                continue
            
            # 获取博客信息
            blog = next((b for b in unassigned_blogs if b['id'] == blog_id), None)
            if not blog:
                continue
            
            # 构建章节信息
            chapter_info = {
                "chapter_index": assignment.get('chapter_index', 1),
                "chapter_title": assignment.get('chapter_title', ''),
                "section_index": assignment.get('section_index', ''),
                "section_title": assignment.get('section_title', ''),
                "blog_id": blog_id,
                "word_count": len(blog.get('markdown_content', '') or '')
            }
            
            if book_id not in book_chapters:
                book_chapters[book_id] = []
            book_chapters[book_id].append(chapter_info)
        
        # 3. 保存章节并更新书籍统计
        for book_id, chapters in book_chapters.items():
            # 获取现有章节
            existing_chapters = self.db.get_book_chapters(book_id)
            
            # 合并章节
            all_chapters = existing_chapters + chapters
            
            # 保存章节
            self.db.save_book_chapters(book_id, all_chapters)
            
            # 同步更新 history_records 表的 book_id
            for chapter in chapters:
                if chapter.get('blog_id'):
                    with self.db.get_connection() as conn:
                        conn.execute(
                            "UPDATE history_records SET book_id = ? WHERE id = ?",
                            (book_id, chapter['blog_id'])
                        )
                        conn.commit()
            
            # 更新书籍统计
            total_word_count = sum(c.get('word_count', 0) for c in all_chapters)
            blogs_count = len([c for c in all_chapters if c.get('blog_id')])
            chapters_count = len(set(c.get('chapter_index') for c in all_chapters))
            
            self.db.update_book(
                book_id,
                chapters_count=chapters_count,
                total_word_count=total_word_count,
                blogs_count=blogs_count
            )
            
            if book_id not in result['new_book_ids']:
                result['books_updated'] += 1
                result['updated_book_ids'].append(book_id)
        
        # 4. 应用大纲更新（智能优化后的大纲）
        for outline_update in decision.get('outline_updates', []):
            book_id = outline_update.get('book_id', '')
            new_outline = outline_update.get('new_outline', {})
            optimization_actions = outline_update.get('optimization_actions', [])
            
            if book_id and new_outline:
                logger.info(f"应用大纲优化: {book_id}, 操作: {optimization_actions}")
                
                # 保存优化后的大纲
                self.db.update_book(
                    book_id,
                    outline=json.dumps(new_outline, ensure_ascii=False)
                )
                
                # 根据新大纲重建章节列表
                new_chapters = self._outline_to_chapters(new_outline)
                if new_chapters:
                    self.db.save_book_chapters(book_id, new_chapters)
                    
                    # 更新统计
                    total_word_count = sum(c.get('word_count', 0) for c in new_chapters)
                    blogs_count = len([c for c in new_chapters if c.get('blog_id')])
                    chapters_count = len(set(c.get('chapter_index') for c in new_chapters))
                    
                    self.db.update_book(
                        book_id,
                        chapters_count=chapters_count,
                        total_word_count=total_word_count,
                        blogs_count=blogs_count
                    )
                
                if book_id not in result['new_book_ids'] and book_id not in result['updated_book_ids']:
                    result['books_updated'] += 1
                    result['updated_book_ids'].append(book_id)
        
        return result
    
    def _outline_to_chapters(self, outline: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        将大纲结构转换为章节列表（支持系列文章）
        
        Args:
            outline: 大纲字典
            
        Returns:
            章节列表
        """
        chapters = []
        
        for chapter in outline.get('chapters', []):
            chapter_index = chapter.get('index', 1)
            chapter_title = chapter.get('title', '')
            
            for section in chapter.get('sections', []):
                section_type = section.get('type', 'single')
                
                if section_type == 'series':
                    # 系列文章：展开为多个章节记录
                    for article in section.get('articles', []):
                        chapters.append({
                            'chapter_index': chapter_index,
                            'chapter_title': chapter_title,
                            'section_index': f"{section.get('index', '')}.{article.get('order', 1)}",
                            'section_title': article.get('title', ''),
                            'blog_id': article.get('blog_id'),
                            'word_count': 0,  # 后续可以从博客获取
                            'series_title': section.get('title', ''),
                            'series_order': article.get('order', 1),
                            'series_total': article.get('total', 1)
                        })
                else:
                    # 单篇文章
                    chapters.append({
                        'chapter_index': chapter_index,
                        'chapter_title': chapter_title,
                        'section_index': section.get('index', ''),
                        'section_title': section.get('title', ''),
                        'blog_id': section.get('blog_id'),
                        'word_count': 0
                    })
        
        return chapters
    
    def rescan_book(self, book_id: str) -> Dict[str, Any]:
        """
        重新扫描单本书籍，智能优化大纲
        
        Args:
            book_id: 书籍 ID
        
        Returns:
            更新结果
        """
        book = self.db.get_book(book_id)
        if not book:
            return {"status": "error", "message": "书籍不存在"}
        
        # 获取书籍关联的博客
        blogs = self.db.get_blogs_by_book(book_id)
        
        if not blogs:
            return {"status": "success", "message": "书籍没有关联的博客"}
        
        # 调用 LLM 重新生成大纲（智能优化）
        if self.llm:
            new_outline = self._regenerate_outline(book, blogs)
            if new_outline:
                # 保存优化后的大纲
                self.db.update_book(book_id, outline=json.dumps(new_outline, ensure_ascii=False))
                
                # 根据新大纲重建章节列表
                new_chapters = self._outline_to_chapters(new_outline)
                if new_chapters:
                    self.db.save_book_chapters(book_id, new_chapters)
                    
                    # 更新统计
                    total_word_count = sum(c.get('word_count', 0) for c in new_chapters)
                    blogs_count = len([c for c in new_chapters if c.get('blog_id')])
                    chapters_count = len(set(c.get('chapter_index') for c in new_chapters))
                    
                    self.db.update_book(
                        book_id,
                        chapters_count=chapters_count,
                        total_word_count=total_word_count,
                        blogs_count=blogs_count
                    )
                    
                    logger.info(f"书籍大纲已优化: {book['title']}, {chapters_count} 章, {blogs_count} 篇博客")
                    
                    # 重新生成首页内容
                    try:
                        from services.homepage_generator_service import HomepageGeneratorService
                        homepage_service = HomepageGeneratorService(self.db, self.llm)
                        homepage_service.generate_homepage(book_id)
                        logger.info(f"书籍首页已更新: {book['title']}")
                    except Exception as e:
                        logger.warning(f"更新首页失败: {e}")
        
        return {
            "status": "success",
            "message": f"书籍 {book['title']} 已更新",
            "blogs_count": len(blogs)
        }
    
    def _regenerate_outline(self, book: Dict[str, Any], blogs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """重新生成书籍大纲（支持智能优化）"""
        if not self.llm:
            return None
        
        blogs_info = []
        for blog in blogs:
            content = blog.get('markdown_content', '') or ''
            
            # 优先使用已保存的摘要
            summary = blog.get('summary', '')
            
            # 提取博客大纲
            outline = blog.get('outline', '')
            outline_summary = ''
            if outline:
                try:
                    outline_data = json.loads(outline) if isinstance(outline, str) else outline
                    sections = outline_data.get('sections', [])
                    outline_summary = ', '.join([s.get('title', '') for s in sections[:5]])
                except:
                    pass
            
            # 如果没有摘要，使用内容前 300 字
            if not summary:
                summary = content[:300].replace('\n', ' ') if content else ""
            
            blog_entry = f"""- 标题: {blog.get('topic', '无标题')}
  ID: {blog['id']}
  字数: {len(content)}
  章节: {outline_summary if outline_summary else '无'}
  摘要: {summary}"""
            blogs_info.append(blog_entry)
        
        prompt = f"""为以下书籍智能优化大纲：

书籍标题: {book['title']}
书籍描述: {book.get('description', '无')}

包含的博客:
{chr(10).join(blogs_info)}

【大纲优化策略】
1. **合并相似章节**：主题相似的博客合并为系列（如 "Redis 入门系列"）
2. **调整章节顺序**：按从入门到进阶的逻辑顺序排列
3. **系列文章标记**：相同主题的多篇博客使用 type: "series"

输出 JSON 格式：
{{
    "chapters": [
        {{
            "index": 1,
            "title": "章节标题",
            "sections": [
                {{"index": "1.1", "title": "单篇标题", "blog_id": "...", "type": "single"}},
                {{
                    "index": "1.2",
                    "title": "系列标题",
                    "type": "series",
                    "articles": [
                        {{"order": 1, "total": 2, "title": "第1篇", "blog_id": "..."}},
                        {{"order": 2, "total": 2, "title": "第2篇", "blog_id": "..."}}
                    ]
                }}
            ]
        }}
    ]
}}

直接返回 JSON。"""
        
        try:
            response = self.llm.chat(messages=[{"role": "user", "content": prompt}])
            response_text = response if isinstance(response, str) else response.get('content', '')
            
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(response_text[json_start:json_end])
        except Exception as e:
            logger.error(f"重新生成大纲失败: {e}")
        
        return None
    
    def generate_book_introduction(self, book_id: str) -> Optional[str]:
        """
        使用 LLM 生成书籍简介
        
        Args:
            book_id: 书籍 ID
        
        Returns:
            生成的简介文本
        """
        book = self.db.get_book(book_id)
        if not book:
            return None
        
        # 获取书籍关联的博客
        blogs = self.db.get_blogs_by_book(book_id)
        
        if not self.llm:
            return f"《{book['title']}》是一本关于{book.get('theme', '技术')}的教程书籍，包含 {len(blogs)} 篇精选博客文章。"
        
        # 构建章节信息
        chapters = self.db.get_book_chapters(book_id)
        chapters_grouped = {}
        for ch in chapters:
            idx = ch.get('chapter_index', 1)
            if idx not in chapters_grouped:
                chapters_grouped[idx] = {
                    'index': idx,
                    'title': ch.get('chapter_title', f'章节 {idx}'),
                    'sections': []
                }
            chapters_grouped[idx]['sections'].append({
                'index': ch.get('section_index', ''),
                'title': ch.get('section_title', '')
            })
        
        chapters_list = list(chapters_grouped.values())
        
        # 使用模板渲染 Prompt
        prompt_manager = get_prompt_manager()
        prompt = prompt_manager.render_book_introduction(
            book_title=book['title'],
            book_theme=book.get('theme', 'general'),
            chapters_count=len(chapters_list),
            chapters=chapters_list
        )
        
        try:
            response = self.llm.chat(messages=[{"role": "user", "content": prompt}])
            introduction = response if isinstance(response, str) else response.get('content', '')
            
            # 更新书籍描述
            if introduction:
                self.db.update_book(book_id, description=introduction.strip())
            
            return introduction.strip()
        except Exception as e:
            logger.error(f"生成书籍简介失败: {e}")
            return None
    
    def generate_book_cover(self, book_id: str) -> Optional[str]:
        """
        使用 nanoBanana 生成书籍封面
        
        Args:
            book_id: 书籍 ID
        
        Returns:
            封面图片 URL
        """
        book = self.db.get_book(book_id)
        if not book:
            logger.error(f"书籍不存在: {book_id}")
            return None
        
        # 检查是否已有封面
        if book.get('cover_image'):
            logger.info(f"书籍已有封面: {book_id}")
            return book['cover_image']
        
        try:
            # 导入图片服务
            from services.image_service import NanoBananaService, AspectRatio, ImageSize
            
            # 获取配置
            api_key = os.getenv('NANO_BANANA_API_KEY')
            api_base = os.getenv('NANO_BANANA_API_BASE', 'https://grsai.dakka.com.cn')
            model = os.getenv('NANO_BANANA_MODEL', 'nano-banana-pro')
            
            if not api_key:
                logger.warning("NANO_BANANA_API_KEY 未配置，跳过封面生成")
                return None
            
            image_service = NanoBananaService(
                api_key=api_key,
                api_base=api_base,
                model=model,
                output_folder="outputs/covers"
            )
            
            # 构建封面生成 Prompt - kawaii 风格
            theme = book.get('theme', 'general')
            theme_icon = THEME_ICONS.get(theme, '📖')
            
            # 主题对应的吉祥物描述
            theme_mascots = {
                'ai': 'a cute kawaii robot mascot with antenna, holding a glowing brain or neural network symbol',
                'web': 'a cute kawaii globe character with happy face, surrounded by connection lines',
                'data': 'a cute kawaii database mascot with charts and graphs floating around',
                'devops': 'a cute kawaii gear/cog character with tools and deployment symbols',
                'security': 'a cute kawaii shield mascot with a lock symbol, looking protective',
                'general': 'a cute kawaii book character with sparkles and stars'
            }
            mascot_desc = theme_mascots.get(theme, theme_mascots['general'])
            
            cover_prompt = f"""A cute kawaii-style mascot illustration for a tech tutorial book cover:

{mascot_desc}

Style requirements:
- Chibi/kawaii proportions with big head and small body
- Warm, friendly color palette (orange, yellow, soft pink, light blue)
- Simple clean background with small decorative elements (stars, gears, sparkles)
- Flat illustration style, soft pastel colors
- Centered composition, logo design suitable for book cover
- Minimalist, friendly and approachable aesthetic
- Professional yet playful tech tutorial vibe
- No text, only the mascot character and decorative elements"""
            
            logger.info(f"开始生成书籍封面: {book['title']}")
            
            # 调用 nanoBanana 生成封面
            result = image_service.generate(
                prompt=cover_prompt,
                aspect_ratio=AspectRatio.PORTRAIT_3_4,
                image_size=ImageSize.SIZE_2K,
                download=True
            )
            
            if result and result.url:
                # 保存封面 URL 到数据库
                # 优先使用本地路径（如果有的话）
                cover_url = f"/outputs/covers/{os.path.basename(result.local_path)}" if result.local_path else result.url
                self.db.update_book(book_id, cover_image=cover_url)
                logger.info(f"书籍封面生成成功: {book_id} -> {cover_url}")
                return cover_url
            else:
                logger.warning(f"书籍封面生成失败: {book_id}")
                return None
                
        except Exception as e:
            logger.error(f"生成书籍封面失败: {e}", exc_info=True)
            return None
    
    def generate_covers_for_all_books(self) -> Dict[str, Any]:
        """
        为所有没有封面的书籍生成封面
        
        Returns:
            生成结果统计
        """
        books = self.db.list_books(status='active')
        
        result = {
            "total": len(books),
            "generated": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }
        
        for book in books:
            if book.get('cover_image'):
                result['skipped'] += 1
                result['details'].append({
                    "book_id": book['id'],
                    "title": book['title'],
                    "status": "skipped",
                    "reason": "已有封面"
                })
                continue
            
            cover_url = self.generate_book_cover(book['id'])
            
            if cover_url:
                result['generated'] += 1
                result['details'].append({
                    "book_id": book['id'],
                    "title": book['title'],
                    "status": "success",
                    "cover_url": cover_url
                })
            else:
                result['failed'] += 1
                result['details'].append({
                    "book_id": book['id'],
                    "title": book['title'],
                    "status": "failed"
                })
        
        logger.info(f"批量生成封面完成: 成功 {result['generated']}, 跳过 {result['skipped']}, 失败 {result['failed']}")
        return result
