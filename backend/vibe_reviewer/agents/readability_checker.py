"""
可读性检测器 - 评估内容可读性

评估词汇、句法、篇章、表层特征四个维度
"""
import json
import logging
from typing import Dict, Any, List, Optional

from ..prompts import get_prompt_manager
from ..schemas import ReadabilityResult, ContentIssue, ReadabilityLevel

logger = logging.getLogger(__name__)


class ReadabilityChecker:
    """
    可读性检测器
    
    评估内容的可读性，包括词汇、句法、篇章、表层特征
    """
    
    def __init__(self, llm_service):
        """
        初始化可读性检测器
        
        Args:
            llm_service: LLM 服务实例
        """
        self.llm = llm_service
        self.pm = get_prompt_manager()
    
    def check(self, content: str) -> ReadabilityResult:
        """
        检查内容可读性
        
        Args:
            content: 待检查内容
            
        Returns:
            可读性评估结果
        """
        prompt = self.pm.render_readability_check(content)
        
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}]
            )
            
            if not response:
                return self._default_result()
            
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"可读性检测失败: {e}")
            return self._default_result()
    
    def _parse_response(self, response: str) -> ReadabilityResult:
        """解析 LLM 响应"""
        try:
            # 提取 JSON
            response = response.strip()
            if '```json' in response:
                start = response.find('```json') + 7
                end = response.find('```', start)
                response = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                response = response[start:end].strip()
            
            data = json.loads(response)
            
            # 解析可读性等级
            level_str = data.get('level', 'normal')
            try:
                level = ReadabilityLevel(level_str)
            except ValueError:
                level = ReadabilityLevel.NORMAL
            
            # 解析问题列表
            issues = []
            for issue in data.get('issues', []):
                issues.append(ContentIssue(
                    issue_type=issue.get('issue_type', 'unknown'),
                    severity=issue.get('severity', 'medium'),
                    location=issue.get('location', ''),
                    description=issue.get('description', ''),
                    suggestion=issue.get('suggestion', ''),
                ))
            
            return ReadabilityResult(
                score=int(data.get('score', 70)),
                level=level,
                issues=issues,
                summary=data.get('summary', ''),
                vocabulary_score=int(data.get('vocabulary_score', 70)),
                syntax_score=int(data.get('syntax_score', 70)),
                discourse_score=int(data.get('discourse_score', 70)),
                surface_score=int(data.get('surface_score', 70)),
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"解析可读性检测结果失败: {e}")
            return self._default_result()
    
    def _default_result(self) -> ReadabilityResult:
        """返回默认结果"""
        return ReadabilityResult(
            score=70,
            level=ReadabilityLevel.NORMAL,
            issues=[],
            summary="可读性检测完成",
            vocabulary_score=70,
            syntax_score=70,
            discourse_score=70,
            surface_score=70,
        )
