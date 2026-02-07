# -*- coding: utf-8 -*-
"""
===================================
舆情分析器 - Sentiment Analyzer
===================================

职责：
1. 分析新闻和市场情绪
2. 提取风险警报
3. 识别利好催化剂
4. 评估舆情对股价影响

核心功能：
- 新闻情感分析
- 风险事件识别
- 利好因素提取
- 市场情绪评估
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class SentimentAnalysisResult:
    """舆情分析结果"""
    code: str
    
    # 核心指标
    sentiment_score: float  # 情绪评分 -100 到 100 (负面到正面)
    sentiment_label: str  # 情绪标签："极度看多"/"看多"/"中性"/"看空"/"极度看空"
    
    # 关键信息
    risk_alerts: List[str] = field(default_factory=list)  # 风险警报
    positive_catalysts: List[str] = field(default_factory=list)  # 利好催化剂
    
    # 详细分析
    news_summary: str = ""  # 新闻摘要
    market_sentiment: str = ""  # 市场情绪描述
    hot_topics: str = ""  # 相关热点话题
    
    # 影响评估
    impact_level: str = ""  # 影响程度："高"/"中"/"低"
    trading_suggestion: str = ""  # 交易建议
    
    # 元数据
    news_count: int = 0  # 新闻数量
    source: str = ""  # 数据来源
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'sentiment_score': self.sentiment_score,
            'sentiment_label': self.sentiment_label,
            'risk_alerts': self.risk_alerts,
            'positive_catalysts': self.positive_catalysts,
            'news_summary': self.news_summary,
            'market_sentiment': self.market_sentiment,
            'hot_topics': self.hot_topics,
            'impact_level': self.impact_level,
            'trading_suggestion': self.trading_suggestion,
            'news_count': self.news_count,
            'source': self.source,
        }


class SentimentAnalyzer:
    """
    舆情分析器
    
    分析新闻、公告、社交媒体等数据，评估市场情绪和舆论影响
    """
    
    # 风险关键词（需要警惕的词汇）
    RISK_KEYWORDS = {
        '减持': 5,
        '抛售': 5,
        '清仓': 6,
        '套现': 4,
        '解禁': 3,
        '业绩预亏': 8,
        '业绩下滑': 6,
        '亏损': 6,
        '立案调查': 9,
        '监管处罚': 8,
        '退市': 10,
        '暂停上市': 9,
        'ST': 7,
        '*ST': 9,
        '财务造假': 10,
        '欺诈': 9,
        '违规': 7,
        '诉讼': 5,
        '仲裁': 4,
        '商誉减值': 6,
        '坏账': 5,
        '债务违约': 9,
        '资金链': 8,
        '破产': 10,
        '重组失败': 7,
        '增发失败': 5,
        '定增失败': 5,
    }
    
    # 利好关键词（积极信号词汇）
    POSITIVE_KEYWORDS = {
        '增持': 5,
        '回购': 6,
        '并购': 5,
        '重组': 6,
        '业绩预增': 7,
        '业绩大增': 8,
        '盈利': 5,
        '营收增长': 6,
        '净利增长': 7,
        '中标': 6,
        '订单': 5,
        '合作': 4,
        '战略合作': 6,
        '研发突破': 7,
        '新技术': 6,
        '新产品': 5,
        '专利': 5,
        '政策支持': 7,
        '补贴': 6,
        '减税': 6,
        '行业利好': 6,
        '国家战略': 7,
        '转型成功': 7,
        '扭亏为盈': 8,
        '资产注入': 7,
        '股权激励': 5,
        '分红': 5,
        '高送转': 6,
    }
    
    def analyze(
        self, 
        news_context: str, 
        stock_code: str,
        stock_name: str = ""
    ) -> SentimentAnalysisResult:
        """
        分析舆情
        
        Args:
            news_context: 新闻上下文（搜索结果或新闻列表）
            stock_code: 股票代码
            stock_name: 股票名称（可选）
            
        Returns:
            SentimentAnalysisResult
        """
        result = SentimentAnalysisResult(
            code=stock_code,
            sentiment_score=0.0,
            sentiment_label="中性",
        )
        
        if not news_context or not news_context.strip():
            logger.warning(f"{stock_code} 无舆情数据")
            result.market_sentiment = "无新闻数据"
            result.impact_level = "低"
            return result
        
        # 1. 提取风险警报
        result.risk_alerts = self.extract_risk_alerts(news_context)
        
        # 2. 提取利好催化剂
        result.positive_catalysts = self.extract_positive_catalysts(news_context)
        
        # 3. 计算情绪评分
        result.sentiment_score = self.calculate_sentiment_score(
            news_context, 
            result.risk_alerts, 
            result.positive_catalysts
        )
        
        # 4. 确定情绪标签
        result.sentiment_label = self._get_sentiment_label(result.sentiment_score)
        
        # 5. 生成新闻摘要
        result.news_summary = self._generate_news_summary(
            news_context, 
            result.risk_alerts, 
            result.positive_catalysts
        )
        
        # 6. 评估市场情绪
        result.market_sentiment = self._assess_market_sentiment(result)
        
        # 7. 提取热点话题
        result.hot_topics = self._extract_hot_topics(news_context)
        
        # 8. 评估影响程度
        result.impact_level = self._assess_impact_level(result)
        
        # 9. 生成交易建议
        result.trading_suggestion = self._generate_trading_suggestion(result)
        
        # 10. 统计新闻数量
        result.news_count = len(news_context.split('\n\n')) if news_context else 0
        result.source = "搜索引擎/新闻API"
        
        return result
    
    def extract_risk_alerts(self, news_context: str) -> List[str]:
        """
        提取风险警报
        
        Args:
            news_context: 新闻上下文
            
        Returns:
            风险警报列表
        """
        alerts = []
        
        if not news_context:
            return alerts
        
        # 按重要性排序关键词
        sorted_keywords = sorted(
            self.RISK_KEYWORDS.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # 查找风险关键词
        for keyword, severity in sorted_keywords:
            if keyword in news_context:
                # 提取相关句子作为上下文
                sentences = self._extract_sentences_with_keyword(news_context, keyword)
                if sentences:
                    emoji = self._get_risk_emoji(severity)
                    alerts.append(f"{emoji} {keyword}：{sentences[0]}")
        
        # 限制数量，返回最重要的几个
        return alerts[:5]
    
    def extract_positive_catalysts(self, news_context: str) -> List[str]:
        """
        提取利好催化剂
        
        Args:
            news_context: 新闻上下文
            
        Returns:
            利好催化剂列表
        """
        catalysts = []
        
        if not news_context:
            return catalysts
        
        # 按重要性排序关键词
        sorted_keywords = sorted(
            self.POSITIVE_KEYWORDS.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # 查找利好关键词
        for keyword, importance in sorted_keywords:
            if keyword in news_context:
                # 提取相关句子作为上下文
                sentences = self._extract_sentences_with_keyword(news_context, keyword)
                if sentences:
                    emoji = self._get_positive_emoji(importance)
                    catalysts.append(f"{emoji} {keyword}：{sentences[0]}")
        
        # 限制数量，返回最重要的几个
        return catalysts[:5]
    
    def calculate_sentiment_score(
        self, 
        news_context: str,
        risk_alerts: List[str],
        positive_catalysts: List[str]
    ) -> float:
        """
        计算情绪评分 (-100 到 100)
        
        评分逻辑：
        1. 统计风险关键词和利好关键词的权重
        2. 风险词汇减分，利好词汇加分
        3. 考虑关键词出现频率
        
        Args:
            news_context: 新闻上下文
            risk_alerts: 风险警报列表
            positive_catalysts: 利好催化剂列表
            
        Returns:
            情绪评分 (-100 到 100)
        """
        if not news_context:
            return 0.0
        
        positive_score = 0.0
        negative_score = 0.0
        
        # 统计利好关键词
        for keyword, weight in self.POSITIVE_KEYWORDS.items():
            count = news_context.count(keyword)
            positive_score += count * weight
        
        # 统计风险关键词
        for keyword, weight in self.RISK_KEYWORDS.items():
            count = news_context.count(keyword)
            negative_score += count * weight
        
        # 归一化到 -100 到 100
        total_score = positive_score - negative_score
        
        # 根据新闻数量调整权重
        news_count = max(1, len(news_context.split('\n\n')))
        normalized_score = total_score / news_count
        
        # 限制在 -100 到 100 之间
        final_score = max(-100, min(100, normalized_score * 5))
        
        return round(final_score, 1)
    
    def _get_sentiment_label(self, score: float) -> str:
        """根据评分获取情绪标签"""
        if score >= 60:
            return "极度看多"
        elif score >= 20:
            return "看多"
        elif score >= -20:
            return "中性"
        elif score >= -60:
            return "看空"
        else:
            return "极度看空"
    
    def _generate_news_summary(
        self, 
        news_context: str,
        risk_alerts: List[str],
        positive_catalysts: List[str]
    ) -> str:
        """生成新闻摘要"""
        summary_parts = []
        
        if positive_catalysts:
            summary_parts.append(f"利好消息：{', '.join([c.split('：')[0].strip('💰🌟⚡✨') for c in positive_catalysts[:3]])}")
        
        if risk_alerts:
            summary_parts.append(f"风险提示：{', '.join([r.split('：')[0].strip('🚨⚠️❗🔴') for r in risk_alerts[:3]])}")
        
        if not summary_parts:
            # 提取新闻标题（简单逻辑）
            lines = [l.strip() for l in news_context.split('\n') if l.strip()]
            if lines:
                summary_parts.append(f"近期新闻：{lines[0][:50]}...")
        
        return "；".join(summary_parts) if summary_parts else "暂无重要新闻"
    
    def _assess_market_sentiment(self, result: SentimentAnalysisResult) -> str:
        """评估市场情绪"""
        score = result.sentiment_score
        
        if score >= 60:
            return "市场情绪极度乐观，多方占优"
        elif score >= 20:
            return "市场情绪偏多，利好因素主导"
        elif score >= -20:
            return "市场情绪中性，多空博弈"
        elif score >= -60:
            return "市场情绪偏空，利空因素主导"
        else:
            return "市场情绪极度悲观，空方占优"
    
    def _extract_hot_topics(self, news_context: str) -> str:
        """提取热点话题（简单关键词提取）"""
        # 这里使用简化逻辑，实际可以使用 NLP 技术提取
        topics = []
        
        # 一些常见的热点主题
        hot_keywords = [
            '人工智能', 'AI', '新能源', '芯片', '半导体',
            '元宇宙', '区块链', '5G', '新基建', '碳中和',
            '新能源汽车', '光伏', '风电', '储能', '氢能',
            '医药', '生物科技', '医疗', '疫苗', '创新药',
        ]
        
        for keyword in hot_keywords:
            if keyword in news_context:
                topics.append(keyword)
        
        return "、".join(topics[:5]) if topics else "暂无明确热点"
    
    def _assess_impact_level(self, result: SentimentAnalysisResult) -> str:
        """评估舆情影响程度"""
        # 根据风险和利好数量评估
        risk_count = len(result.risk_alerts)
        positive_count = len(result.positive_catalysts)
        abs_score = abs(result.sentiment_score)
        
        if abs_score >= 60 or risk_count >= 3 or positive_count >= 3:
            return "高"
        elif abs_score >= 20 or risk_count >= 1 or positive_count >= 1:
            return "中"
        else:
            return "低"
    
    def _generate_trading_suggestion(self, result: SentimentAnalysisResult) -> str:
        """生成交易建议"""
        score = result.sentiment_score
        risk_count = len(result.risk_alerts)
        positive_count = len(result.positive_catalysts)
        
        if risk_count >= 3:
            return "重大利空，建议规避或减仓"
        elif risk_count >= 1 and score < 0:
            return "存在利空，谨慎操作，降低仓位"
        elif positive_count >= 3 and score > 40:
            return "多重利好，可积极关注建仓机会"
        elif positive_count >= 1 and score > 0:
            return "有利好催化，可适当参与"
        elif abs(score) < 20:
            return "舆情中性，关注技术面和基本面"
        else:
            return "综合研判，结合技术面和基本面决策"
    
    def _extract_sentences_with_keyword(
        self, 
        text: str, 
        keyword: str, 
        max_length: int = 80
    ) -> List[str]:
        """提取包含关键词的句子"""
        sentences = []
        
        # 分句（简单逻辑）
        text_sentences = re.split(r'[。！？\n]', text)
        
        for sentence in text_sentences:
            if keyword in sentence:
                # 截取合适长度
                sentence = sentence.strip()
                if len(sentence) > max_length:
                    # 尝试从关键词前后截取
                    idx = sentence.find(keyword)
                    start = max(0, idx - 30)
                    end = min(len(sentence), idx + 50)
                    sentence = "..." + sentence[start:end] + "..."
                
                sentences.append(sentence)
                
                if len(sentences) >= 1:  # 只返回第一个相关句子
                    break
        
        return sentences
    
    def _get_risk_emoji(self, severity: int) -> str:
        """根据严重程度返回风险emoji"""
        if severity >= 8:
            return "🚨"  # 严重风险
        elif severity >= 5:
            return "⚠️"  # 警告
        else:
            return "❗"  # 注意
    
    def _get_positive_emoji(self, importance: int) -> str:
        """根据重要性返回利好emoji"""
        if importance >= 7:
            return "💰"  # 重大利好
        elif importance >= 5:
            return "🌟"  # 利好
        else:
            return "✨"  # 小利好
    
    def format_analysis(self, result: SentimentAnalysisResult) -> str:
        """
        格式化分析结果为文本
        
        Args:
            result: 分析结果
            
        Returns:
            格式化的分析文本
        """
        lines = [
            f"=== {result.code} 舆情分析 ===",
            f"",
            f"📰 舆情评分: {result.sentiment_score:+.1f} / 100",
            f"   情绪标签: {result.sentiment_label}",
            f"   影响程度: {result.impact_level}",
            f"",
            f"📊 市场情绪:",
            f"   {result.market_sentiment}",
            f"",
        ]
        
        if result.positive_catalysts:
            lines.append(f"💰 利好催化剂:")
            for catalyst in result.positive_catalysts:
                lines.append(f"   {catalyst}")
            lines.append(f"")
        
        if result.risk_alerts:
            lines.append(f"⚠️ 风险警报:")
            for alert in result.risk_alerts:
                lines.append(f"   {alert}")
            lines.append(f"")
        
        if result.hot_topics:
            lines.append(f"🔥 相关热点:")
            lines.append(f"   {result.hot_topics}")
            lines.append(f"")
        
        lines.append(f"💡 交易建议:")
        lines.append(f"   {result.trading_suggestion}")
        lines.append(f"")
        lines.append(f"📝 新闻摘要:")
        lines.append(f"   {result.news_summary}")
        
        return "\n".join(lines)


def analyze_sentiment(
    news_context: str, 
    stock_code: str,
    stock_name: str = ""
) -> SentimentAnalysisResult:
    """
    便捷函数：分析舆情
    
    Args:
        news_context: 新闻上下文
        stock_code: 股票代码
        stock_name: 股票名称（可选）
        
    Returns:
        SentimentAnalysisResult
    """
    analyzer = SentimentAnalyzer()
    return analyzer.analyze(news_context, stock_code, stock_name)


if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 模拟新闻数据
    test_news = """
    某公司发布2024年度业绩预增公告，预计净利润同比增长80%以上
    
    公司与国内知名企业达成战略合作协议，共同开拓新能源市场
    
    公司获得政府补贴5000万元，用于新技术研发
    
    公司董事长增持公司股份，彰显对未来发展信心
    """
    
    # 分析
    result = analyze_sentiment(test_news, stock_code="600519", stock_name="贵州茅台")
    
    print(SentimentAnalyzer().format_analysis(result))
