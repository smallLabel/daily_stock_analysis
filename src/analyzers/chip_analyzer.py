# -*- coding: utf-8 -*-
"""
===================================
筹码分析器 - Chip Distribution Analyzer
===================================

职责：
1. 分析筹码分布数据
2. 评估筹码健康状况
3. 提供筹码结构洞察

核心指标：
- 获利比例：反映市场获利/套牢情况
- 平均成本：市场平均持仓成本
- 筹码集中度：主力控盘程度
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from data_provider.realtime_types import ChipDistribution

logger = logging.getLogger(__name__)


@dataclass
class ChipAnalysisResult:
    """筹码分析结果"""
    code: str
    
    # 原始筹码数据
    profit_ratio: float  # 获利比例 0-1
    avg_cost: float  # 平均成本
    concentration_90: float  # 90%筹码集中度
    concentration_70: float  # 70%筹码集中度
    cost_90_low: float  # 90%成本下限
    cost_90_high: float  # 90%成本上限
    
    # 分析结果
    chip_health: str  # 健康状态："健康"/"一般"/"警惕"
    health_score: float  # 健康评分 0-100
    
    # 详细分析
    profit_status: str  # 获利状态描述
    concentration_status: str  # 集中度状态描述
    cost_position: str  # 成本位置描述
    
    # 综合分析
    analysis_summary: str  # 分析摘要
    trading_implications: str  # 交易含义
    risk_points: list = None  # 风险点
    
    def __post_init__(self):
        if self.risk_points is None:
            self.risk_points = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'profit_ratio': self.profit_ratio,
            'avg_cost': self.avg_cost,
            'concentration_90': self.concentration_90,
            'concentration_70': self.concentration_70,
            'cost_90_low': self.cost_90_low,
            'cost_90_high': self.cost_90_high,
            'chip_health': self.chip_health,
            'health_score': self.health_score,
            'profit_status': self.profit_status,
            'concentration_status': self.concentration_status,
            'cost_position': self.cost_position,
            'analysis_summary': self.analysis_summary,
            'trading_implications': self.trading_implications,
            'risk_points': self.risk_points,
        }


class ChipAnalyzer:
    """
    筹码分析器
    
    分析股票的筹码分布情况，评估主力控盘和获利盘压力
    """
    
    # 筹码健康评分权重
    PROFIT_WEIGHT = 0.4      # 获利比例权重
    CONCENTRATION_WEIGHT = 0.3  # 集中度权重
    COST_POSITION_WEIGHT = 0.3  # 成本位置权重
    
    # 阈值配置
    CONCENTRATION_TIGHT = 0.08   # 高度集中阈值
    CONCENTRATION_MODERATE = 0.15  # 较集中阈值
    CONCENTRATION_LOOSE = 0.25   # 分散阈值
    
    PROFIT_HIGH = 0.9          # 获利盘高阈值
    PROFIT_MEDIUM_HIGH = 0.7   # 获利盘较高阈值
    PROFIT_MEDIUM = 0.5        # 获利盘中等阈值
    PROFIT_LOW = 0.3           # 套牢盘较多阈值
    
    def analyze(
        self, 
        chip_data: ChipDistribution, 
        current_price: float
    ) -> Optional[ChipAnalysisResult]:
        """
        分析筹码分布
        
        Args:
            chip_data: 筹码分布数据
            current_price: 当前股价
            
        Returns:
            ChipAnalysisResult 或 None（数据无效时）
        """
        if not chip_data or not current_price:
            logger.warning("筹码数据或当前价格无效")
            return None
        
        # 创建结果对象
        result = ChipAnalysisResult(
            code=chip_data.code,
            profit_ratio=chip_data.profit_ratio,
            avg_cost=chip_data.avg_cost,
            concentration_90=chip_data.concentration_90,
            concentration_70=chip_data.concentration_70,
            cost_90_low=chip_data.cost_90_low,
            cost_90_high=chip_data.cost_90_high,
            chip_health="",
            health_score=0.0,
            profit_status="",
            concentration_status="",
            cost_position="",
            analysis_summary="",
            trading_implications="",
        )
        
        # 1. 分析获利比例
        self._analyze_profit_ratio(result)
        
        # 2. 分析筹码集中度
        self._analyze_concentration(result)
        
        # 3. 分析成本位置
        self._analyze_cost_position(result, current_price)
        
        # 4. 计算健康评分
        result.health_score = self.calculate_health_score(result, current_price)
        
        # 5. 确定健康等级
        result.chip_health = self.get_chip_health(result.health_score)
        
        # 6. 生成综合分析
        self._generate_summary(result, current_price)
        
        return result
    
    def _analyze_profit_ratio(self, result: ChipAnalysisResult) -> None:
        """分析获利比例"""
        ratio = result.profit_ratio
        
        if ratio >= self.PROFIT_HIGH:
            result.profit_status = f"获利盘极高({ratio:.1%})，获利回吐压力大"
            result.risk_points.append("⚠️ 获利盘过重(>90%)，警惕获利回吐")
        elif ratio >= self.PROFIT_MEDIUM_HIGH:
            result.profit_status = f"获利盘较高({ratio:.1%})，适度获利盘压力"
            result.risk_points.append("⚡ 获利盘较高(70-90%)，注意回调风险")
        elif ratio >= self.PROFIT_MEDIUM:
            result.profit_status = f"获利盘中等({ratio:.1%})，盈亏相对平衡"
        elif ratio >= self.PROFIT_LOW:
            result.profit_status = f"套牢盘较多({ratio:.1%}获利)，上行压力轻"
        else:
            result.profit_status = f"套牢盘极重({ratio:.1%}获利)，反弹动力强"
    
    def _analyze_concentration(self, result: ChipAnalysisResult) -> None:
        """分析筹码集中度"""
        conc = result.concentration_90
        
        if conc < self.CONCENTRATION_TIGHT:
            result.concentration_status = f"筹码高度集中({conc:.1%})，主力控盘明显"
        elif conc < self.CONCENTRATION_MODERATE:
            result.concentration_status = f"筹码较集中({conc:.1%})，有一定控盘"
        elif conc < self.CONCENTRATION_LOOSE:
            result.concentration_status = f"筹码集中度中等({conc:.1%})"
        else:
            result.concentration_status = f"筹码较分散({conc:.1%})，散户占比高"
            result.risk_points.append("⚠️ 筹码分散，主力控盘能力弱")
    
    def _analyze_cost_position(
        self, 
        result: ChipAnalysisResult, 
        current_price: float
    ) -> None:
        """分析成本位置关系"""
        if result.avg_cost <= 0:
            result.cost_position = "平均成本数据缺失"
            return
        
        cost_diff = (current_price - result.avg_cost) / result.avg_cost * 100
        
        if cost_diff > 20:
            result.cost_position = f"现价高于平均成本{cost_diff:.1f}%，获利空间大"
            result.risk_points.append(f"⚠️ 现价高出成本{cost_diff:.1f}%，获利盘压力")
        elif cost_diff > 15:
            result.cost_position = f"现价高于平均成本{cost_diff:.1f}%，健康上涨"
        elif cost_diff > 5:
            result.cost_position = f"现价略高于成本{cost_diff:.1f}%，温和上涨"
        elif cost_diff > -5:
            result.cost_position = f"现价接近平均成本({cost_diff:+.1f}%)，筹码洗盘充分"
        elif cost_diff > -15:
            result.cost_position = f"现价低于平均成本{abs(cost_diff):.1f}%，套牢盘重"
        else:
            result.cost_position = f"现价严重低于成本{abs(cost_diff):.1f}%，深度套牢"
    
    def calculate_health_score(
        self, 
        result: ChipAnalysisResult, 
        current_price: float
    ) -> float:
        """
        计算筹码健康评分 (0-100)
        
        评分逻辑：
        1. 获利比例评分：50-70%获利最健康（避免过高获利盘压力）
        2. 集中度评分：筹码越集中越好
        3. 成本位置评分：现价高于成本5-15%最健康
        """
        score = 0.0
        
        # 1. 获利比例评分 (0-40分)
        profit_score = self._score_profit_ratio(result.profit_ratio)
        score += profit_score * self.PROFIT_WEIGHT * 100
        
        # 2. 集中度评分 (0-30分)
        conc_score = self._score_concentration(result.concentration_90)
        score += conc_score * self.CONCENTRATION_WEIGHT * 100
        
        # 3. 成本位置评分 (0-30分)
        if result.avg_cost > 0:
            cost_score = self._score_cost_position(current_price, result.avg_cost)
            score += cost_score * self.COST_POSITION_WEIGHT * 100
        
        return round(score, 1)
    
    def _score_profit_ratio(self, ratio: float) -> float:
        """
        获利比例评分 (0-1)
        
        最佳区间：0.5-0.7 (50-70%获利)
        """
        if 0.5 <= ratio <= 0.7:
            return 1.0  # 最佳区间
        elif 0.4 <= ratio < 0.5 or 0.7 < ratio <= 0.8:
            return 0.8  # 次优区间
        elif 0.3 <= ratio < 0.4 or 0.8 < ratio <= 0.9:
            return 0.6  # 一般
        elif ratio < 0.3:
            return 0.5  # 套牢盘重，有反弹潜力
        else:  # ratio > 0.9
            return 0.3  # 获利盘过重，风险大
    
    def _score_concentration(self, concentration: float) -> float:
        """
        筹码集中度评分 (0-1)
        
        集中度越小越好（越集中）
        """
        if concentration < self.CONCENTRATION_TIGHT:
            return 1.0  # 高度集中
        elif concentration < self.CONCENTRATION_MODERATE:
            return 0.8  # 较集中
        elif concentration < self.CONCENTRATION_LOOSE:
            return 0.5  # 中等
        else:
            return 0.3  # 分散
    
    def _score_cost_position(self, current_price: float, avg_cost: float) -> float:
        """
        成本位置评分 (0-1)
        
        最佳区间：现价高于成本 5-15%
        """
        if avg_cost <= 0:
            return 0.5  # 默认中等
        
        diff_pct = (current_price - avg_cost) / avg_cost * 100
        
        if 5 <= diff_pct <= 15:
            return 1.0  # 最佳区间
        elif 0 <= diff_pct < 5 or 15 < diff_pct <= 20:
            return 0.8  # 次优
        elif -5 <= diff_pct < 0 or 20 < diff_pct <= 30:
            return 0.6  # 一般
        elif diff_pct < -15 or diff_pct > 40:
            return 0.2  # 风险区间
        else:
            return 0.4  # 偏离较大
    
    def get_chip_health(self, score: float) -> str:
        """
        根据评分确定健康等级
        
        Args:
            score: 健康评分 (0-100)
            
        Returns:
            健康等级："健康"/"一般"/"警惕"
        """
        if score >= 70:
            return "健康"
        elif score >= 50:
            return "一般"
        else:
            return "警惕"
    
    def _generate_summary(
        self, 
        result: ChipAnalysisResult, 
        current_price: float
    ) -> None:
        """生成综合分析摘要"""
        # 分析摘要
        summary_parts = [
            result.profit_status,
            result.concentration_status,
            result.cost_position,
        ]
        result.analysis_summary = "；".join(summary_parts)
        
        # 交易含义
        implications = []
        
        # 根据获利比例
        if result.profit_ratio > 0.8:
            implications.append("获利盘压力大，适合减仓或止盈")
        elif result.profit_ratio < 0.4:
            implications.append("套牢盘重，反弹动力强，可考虑建仓")
        else:
            implications.append("盈亏相对平衡，关注技术形态")
        
        # 根据集中度
        if result.concentration_90 < self.CONCENTRATION_MODERATE:
            implications.append("筹码集中，主力控盘，跟随主力操作")
        else:
            implications.append("筹码分散，市场博弈激烈，注意波动")
        
        # 根据成本位置
        if result.avg_cost > 0:
            cost_diff = (current_price - result.avg_cost) / result.avg_cost * 100
            if 5 <= cost_diff <= 20:
                implications.append("成本位支撑良好，可持仓")
            elif cost_diff > 20:
                implications.append("获利空间已大，注意回调风险")
            elif cost_diff < -10:
                implications.append("深度套牢，等待反弹或割肉")
        
        result.trading_implications = "；".join(implications)
    
    def format_analysis(self, result: ChipAnalysisResult) -> str:
        """
        格式化分析结果为文本
        
        Args:
            result: 分析结果
            
        Returns:
            格式化的分析文本
        """
        lines = [
            f"=== {result.code} 筹码分析 ===",
            f"",
            f"💎 筹码健康: {result.chip_health} ({result.health_score}/100)",
            f"",
            f"📊 基础数据:",
            f"   获利比例: {result.profit_ratio:.1%}",
            f"   平均成本: {result.avg_cost:.2f}",
            f"   90%筹码集中度: {result.concentration_90:.1%}",
            f"   90%成本区间: {result.cost_90_low:.2f} - {result.cost_90_high:.2f}",
            f"",
            f"📈 分析结果:",
            f"   {result.profit_status}",
            f"   {result.concentration_status}",
            f"   {result.cost_position}",
            f"",
            f"💡 交易含义:",
            f"   {result.trading_implications}",
        ]
        
        if result.risk_points:
            lines.append(f"")
            lines.append(f"⚠️ 风险提示:")
            for risk in result.risk_points:
                lines.append(f"   {risk}")
        
        lines.append(f"")
        lines.append(f"📝 综合分析:")
        lines.append(f"   {result.analysis_summary}")
        
        return "\n".join(lines)


def analyze_chip(
    chip_data: ChipDistribution, 
    current_price: float
) -> Optional[ChipAnalysisResult]:
    """
    便捷函数：分析筹码分布
    
    Args:
        chip_data: 筹码分布数据
        current_price: 当前股价
        
    Returns:
        ChipAnalysisResult 或 None
    """
    analyzer = ChipAnalyzer()
    return analyzer.analyze(chip_data, current_price)


if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 模拟筹码数据
    test_chip = ChipDistribution(
        code="600519",
        profit_ratio=0.65,
        avg_cost=1500.0,
        concentration_90=0.12,
        concentration_70=0.08,
        cost_90_low=1400.0,
        cost_90_high=1600.0,
    )
    
    # 分析
    result = analyze_chip(test_chip, current_price=1650.0)
    
    if result:
        print(ChipAnalyzer().format_analysis(result))
