"""
Coder Agent - 代码生成
"""

import json
import logging
import re
from typing import Dict, Any, List

from ..prompts.prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)


class CoderAgent:
    """
    代码示例师 - 负责生成代码示例和输出
    """
    
    def __init__(self, llm_client):
        """
        初始化 Coder Agent
        
        Args:
            llm_client: LLM 客户端
        """
        self.llm = llm_client
    
    def generate_code(
        self,
        code_description: str,
        context: str,
        language: str = "python",
        complexity: str = "medium"
    ) -> Dict[str, Any]:
        """
        生成代码示例
        
        Args:
            code_description: 代码描述
            context: 所在章节上下文
            language: 编程语言
            complexity: 复杂度
            
        Returns:
            代码块字典
        """
        pm = get_prompt_manager()
        prompt = pm.render_coder(
            code_description=code_description,
            context=context,
            language=language,
            complexity=complexity
        )
        
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response)
            return {
                "code": result.get("code_block", ""),
                "output": result.get("output_block", ""),
                "explanation": result.get("explanation", ""),
                "language": language
            }
            
        except Exception as e:
            logger.error(f"代码生成失败: {e}")
            raise
    
    def extract_code_placeholders(self, content: str) -> List[Dict[str, str]]:
        """
        从内容中提取代码占位符
        
        Args:
            content: 章节内容
            
        Returns:
            代码占位符列表
        """
        # 匹配 [CODE: code_id - description] 格式
        pattern = r'\[CODE:\s*(\w+)\s*-\s*([^\]]+)\]'
        matches = re.findall(pattern, content)
        
        placeholders = []
        for code_id, description in matches:
            placeholders.append({
                "id": code_id,
                "description": description.strip()
            })
        
        return placeholders
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行代码生成
        
        Args:
            state: 共享状态
            
        Returns:
            更新后的状态
        """
        if state.get('error'):
            logger.error(f"前置步骤失败，跳过代码生成: {state.get('error')}")
            state['code_blocks'] = []
            return state
        
        sections = state.get('sections', [])
        if not sections:
            logger.warning("没有章节内容，跳过代码生成")
            state['code_blocks'] = []
            return state
        
        logger.info("开始生成代码示例")
        
        code_blocks = []
        code_id_counter = 1
        
        for section in sections:
            content = section.get('content', '')
            section_title = section.get('title', '')
            
            # 提取代码占位符
            placeholders = self.extract_code_placeholders(content)
            
            for placeholder in placeholders:
                try:
                    code = self.generate_code(
                        code_description=placeholder['description'],
                        context=f"章节: {section_title}",
                        language="python",
                        complexity="medium"
                    )
                    
                    code_block = {
                        "id": placeholder['id'],
                        "code": code.get('code', ''),
                        "output": code.get('output', ''),
                        "explanation": code.get('explanation', ''),
                        "language": code.get('language', 'python')
                    }
                    code_blocks.append(code_block)
                    
                    # 更新章节的 code_ids
                    if 'code_ids' not in section:
                        section['code_ids'] = []
                    section['code_ids'].append(placeholder['id'])
                    
                    logger.info(f"代码生成完成: {placeholder['id']}")
                    code_id_counter += 1
                    
                except Exception as e:
                    logger.error(f"代码生成失败 [{placeholder['id']}]: {e}")
        
        state['code_blocks'] = code_blocks
        logger.info(f"代码生成完成: {len(code_blocks)} 个代码块")
        
        return state
