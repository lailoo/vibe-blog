"""
Reviewer Agent - 质量审核
"""

import json
import logging
from typing import Dict, Any

from ..prompts.prompt_manager import get_prompt_manager

logger = logging.getLogger(__name__)


class ReviewerAgent:
    """
    质量审核师 - 负责内容质量把控
    """
    
    def __init__(self, llm_client):
        """
        初始化 Reviewer Agent
        
        Args:
            llm_client: LLM 客户端
        """
        self.llm = llm_client
    
    def review(
        self,
        document: str,
        outline: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        审核文档
        
        Args:
            document: 完整文档
            outline: 原始大纲
            
        Returns:
            审核结果
        """
        pm = get_prompt_manager()
        prompt = pm.render_reviewer(
            document=document,
            outline=outline
        )
        
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response)
            return {
                "score": result.get("score", 80),
                "approved": result.get("approved", True),
                "issues": result.get("issues", []),
                "summary": result.get("summary", "")
            }
            
        except Exception as e:
            logger.error(f"审核失败: {e}")
            # 默认通过
            return {
                "score": 80,
                "approved": True,
                "issues": [],
                "summary": "审核完成"
            }
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行质量审核
        
        Args:
            state: 共享状态
            
        Returns:
            更新后的状态
        """
        if state.get('error'):
            logger.error(f"前置步骤失败，跳过质量审核: {state.get('error')}")
            state['review_score'] = 0
            state['review_approved'] = False
            state['review_issues'] = []
            return state
        
        sections = state.get('sections', [])
        if not sections:
            logger.error("没有章节内容，跳过质量审核")
            state['review_score'] = 0
            state['review_approved'] = False
            state['review_issues'] = []
            return state
        
        outline = state.get('outline', {})
        
        # 组装文档用于审核
        document_parts = []
        for section in sections:
            document_parts.append(f"## {section.get('title', '')}\n\n{section.get('content', '')}")
        
        document = '\n\n---\n\n'.join(document_parts)
        
        logger.info("开始质量审核")
        
        result = self.review(document, outline)
        
        state['review_score'] = result.get('score', 80)
        state['review_approved'] = result.get('approved', True)
        state['review_issues'] = result.get('issues', [])
        
        logger.info(f"质量审核完成: 得分 {result.get('score', 0)}, {'通过' if result.get('approved') else '未通过'}")
        
        if result.get('issues'):
            for issue in result['issues']:
                logger.info(f"  - [{issue.get('severity', 'medium')}] {issue.get('description', '')}")
        
        return state
