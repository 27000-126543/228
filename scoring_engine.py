from typing import Dict, Tuple, List
from datetime import date
from config import SCORING_WEIGHTS, SUPPLIER_LEVELS


class QualitySystemScorer:
    def __init__(self):
        pass

    def score(self, qualifications: List, quality_issues: List) -> Tuple[float, Dict]:
        score = 0
        details = {}

        has_iso9001 = any(q.qual_type == 'ISO9001' and q.is_verified for q in qualifications)
        if has_iso9001:
            score += 40
            details['iso9001'] = 40
        else:
            details['iso9001'] = 0

        has_iso45001 = any(q.qual_type == 'ISO45001' and q.is_verified for q in qualifications)
        if has_iso45001:
            score += 20
            details['iso45001'] = 20
        else:
            details['iso45001'] = 0

        verified_count = sum(1 for q in qualifications if q.is_verified)
        if verified_count >= 5:
            score += 20
        elif verified_count >= 3:
            score += 10
        elif verified_count >= 1:
            score += 5
        details['verified_count'] = min(20, verified_count * 4)

        major_issues = sum(1 for issue in quality_issues if issue.severity == 'major' and not issue.is_resolved)
        if major_issues == 0:
            score += 20
        elif major_issues == 1:
            score += 10
        else:
            score -= 20 * major_issues
        details['quality_issues_penalty'] = max(-40, 20 - major_issues * 20)

        return max(0, min(100, score)), details


class EnvironmentalScorer:
    def __init__(self):
        pass

    def score(self, qualifications: List) -> Tuple[float, Dict]:
        score = 0
        details = {}

        has_iso14001 = any(q.qual_type == 'ISO14001' and q.is_verified for q in qualifications)
        if has_iso14001:
            score += 50
            details['iso14001'] = 50
        else:
            details['iso14001'] = 0

        has_business_license = any(q.qual_type == 'BusinessLicense' and q.is_verified for q in qualifications)
        if has_business_license:
            score += 25
            details['business_license'] = 25
        else:
            details['business_license'] = 0

        env_certs = sum(1 for q in qualifications if '环境' in q.qual_type or '环保' in q.qual_type and q.is_verified)
        if env_certs >= 3:
            score += 25
        elif env_certs >= 2:
            score += 15
        elif env_certs >= 1:
            score += 5
        details['additional_env_certs'] = min(25, env_certs * 8)

        return max(0, min(100, score)), details


class FinancialScorer:
    def __init__(self):
        pass

    def score(self, supplier_data: Dict, qualifications: List) -> Tuple[float, Dict]:
        score = 0
        details = {}

        registered_capital = supplier_data.get('registered_capital', 0)
        if registered_capital >= 50000000:
            score += 30
        elif registered_capital >= 10000000:
            score += 20
        elif registered_capital >= 5000000:
            score += 10
        else:
            score += 5
        details['registered_capital'] = min(30, max(5, registered_capital // 1666666))

        establishment_date = supplier_data.get('establishment_date')
        if establishment_date:
            years = (date.today() - establishment_date).days / 365
            if years >= 15:
                score += 25
            elif years >= 10:
                score += 20
            elif years >= 5:
                score += 10
            elif years >= 3:
                score += 5
            details['establishment_years'] = min(25, max(0, years * 1.67))
        else:
            details['establishment_years'] = 0

        has_financial_report = any(q.qual_type == 'Financial' and q.is_verified for q in qualifications)
        if has_financial_report:
            score += 25
            details['financial_report'] = 25
        else:
            details['financial_report'] = 0

        industry = supplier_data.get('industry', '')
        if industry in ['制造业', '高新技术', '电子信息']:
            score += 20
        elif industry in ['服务业', '贸易']:
            score += 10
        details['industry_bonus'] = 20 if industry in ['制造业', '高新技术', '电子信息'] else (10 if industry in ['服务业', '贸易'] else 0)

        return max(0, min(100, score)), details


class PerformanceScorer:
    def __init__(self):
        pass

    def score(self, performance_records: List, period_months: int = 12) -> Tuple[float, Dict]:
        if not performance_records:
            return 60, {'note': '无历史绩效数据，给予基础分'}

        score = 0
        details = {}

        recent_records = sorted(performance_records, key=lambda x: (x.record_year, x.record_month), reverse=True)[:period_months]

        if recent_records:
            avg_on_time = sum(r.on_time_rate or 0 for r in recent_records) / len(recent_records)
            if avg_on_time >= 98:
                score += 35
            elif avg_on_time >= 95:
                score += 25
            elif avg_on_time >= 90:
                score += 15
            elif avg_on_time >= 80:
                score += 5
            details['on_time_rate'] = min(35, max(0, (avg_on_time - 80) * 1.75))

            avg_quality = sum(r.quality_pass_rate or 0 for r in recent_records) / len(recent_records)
            if avg_quality >= 99:
                score += 35
            elif avg_quality >= 97:
                score += 25
            elif avg_quality >= 95:
                score += 15
            elif avg_quality >= 90:
                score += 5
            details['quality_pass_rate'] = min(35, max(0, (avg_quality - 90) * 3.5))

            avg_response = sum(r.response_time_hours or 24 for r in recent_records) / len(recent_records)
            if avg_response <= 2:
                score += 30
            elif avg_response <= 4:
                score += 20
            elif avg_response <= 8:
                score += 10
            elif avg_response <= 24:
                score += 5
            details['response_time'] = min(30, max(0, (24 - avg_response) * 1.36))

        return max(0, min(100, score)), details


class ScoringEngine:
    def __init__(self):
        self.quality_scorer = QualitySystemScorer()
        self.environmental_scorer = EnvironmentalScorer()
        self.financial_scorer = FinancialScorer()
        self.performance_scorer = PerformanceScorer()
        self.weights = SCORING_WEIGHTS

    def calculate_admission_score(self, supplier, qualifications: List, quality_issues: List) -> Dict:
        quality_score, quality_details = self.quality_scorer.score(qualifications, quality_issues)
        environmental_score, env_details = self.environmental_scorer.score(qualifications)
        
        supplier_data = {
            'registered_capital': supplier.registered_capital,
            'establishment_date': supplier.establishment_date,
            'industry': supplier.industry
        }
        financial_score, financial_details = self.financial_scorer.score(supplier_data, qualifications)

        total_score = (
            quality_score * self.weights['quality_system'] +
            environmental_score * self.weights['environmental'] +
            financial_score * self.weights['financial']
        )

        return {
            'total_score': round(total_score, 2),
            'quality_score': round(quality_score, 2),
            'environmental_score': round(environmental_score, 2),
            'financial_score': round(financial_score, 2),
            'quality_details': quality_details,
            'environmental_details': env_details,
            'financial_details': financial_details
        }

    def calculate_performance_score(self, performance_records: List) -> Dict:
        perf_score, perf_details = self.performance_scorer.score(performance_records)
        return {
            'performance_score': round(perf_score, 2),
            'performance_details': perf_details
        }

    def calculate_yearly_review_score(self, supplier, qualifications: List, quality_issues: List, performance_records: List) -> Dict:
        admission_scores = self.calculate_admission_score(supplier, qualifications, quality_issues)
        perf_scores = self.calculate_performance_score(performance_records)

        total_score = (
            admission_scores['total_score'] * 0.4 +
            perf_scores['performance_score'] * 0.6
        )

        return {
            'total_score': round(total_score, 2),
            'admission_score': admission_scores['total_score'],
            'performance_score': perf_scores['performance_score'],
            'breakdown': {
                'admission': admission_scores,
                'performance': perf_scores
            }
        }

    def determine_level(self, total_score: float) -> Tuple[str, str]:
        for level, config in sorted(SUPPLIER_LEVELS.items(), key=lambda x: x[1]['min_score'], reverse=True):
            if total_score >= config['min_score']:
                return level, config['description']
        return 'D', '不合格供应商'

    def get_level_score(self, level: str) -> float:
        if level in SUPPLIER_LEVELS:
            return (SUPPLIER_LEVELS[level]['min_score'] + SUPPLIER_LEVELS[level]['max_score']) / 2
        return 0
