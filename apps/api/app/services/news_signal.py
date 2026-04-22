from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from statistics import mean
from typing import Iterable
from xml.etree import ElementTree as ET

import httpx

from app.schemas.portfolio import UserMandate
from app.services.mandate import normalize_sector_code


REGION_KEYWORDS = {
    "Middle East": {"middle east", "gulf", "opec", "iran", "israel", "red sea", "saudi"},
    "Europe": {"europe", "eu", "germany", "france", "uk", "united kingdom"},
    "India": {"india", "indian", "rbi", "sebi", "nse", "monsoon", "rupee"},
    "US": {"us", "usa", "united states", "fed", "federal reserve", "nasdaq"},
    "China": {"china", "chinese", "beijing", "yuan"},
}

SECTOR_KEYWORDS = {
    "Energy": {"crude", "oil", "gas", "refinery", "power", "lng", "fuel"},
    "Auto": {"auto", "vehicle", "passenger car", "tractor", "ev", "battery"},
    "IT": {"software", "it services", "technology spending", "cloud", "outsourcing"},
    "Banking": {"bank", "credit", "loan", "npa", "deposit", "yield"},
    "Finance": {"nbfc", "lending", "insurance", "wealth", "fintech"},
    "Pharma": {"pharma", "drug", "usfda", "healthcare", "api"},
    "FMCG": {"consumer", "staples", "pricing", "rural demand"},
    "Infra": {"capex", "infrastructure", "construction", "rail", "defence order"},
    "Telecom": {"telecom", "tariff", "spectrum", "subscriber"},
    "Metals": {"metal", "steel", "aluminium", "copper", "coal", "commodity"},
    "Real Estate": {"housing", "real estate", "property", "mortgage"},
    "Chemicals": {"chemical", "specialty chemical"},
    "Consumer Durables": {"durable", "appliance", "electronics"},
    "Tech/Internet": {"internet", "e-commerce", "delivery app", "platform"},
    "Index": {"market", "benchmark", "index"},
}

POSITIVE_KEYWORDS = {
    "surge", "beats", "approval", "cut", "boost", "tailwind", "recovery",
    "growth", "rally", "order win", "supportive", "expansion", "eases",
}
NEGATIVE_KEYWORDS = {
    "war", "conflict", "sanction", "shock", "pressure", "cuts", "downgrade",
    "miss", "outflow", "tariff", "slump", "disruption", "attack", "volatility",
}
HIGH_IMPACT_KEYWORDS = {
    "war", "sanction", "opec", "crude", "tariff", "fda", "rbi", "fed",
    "conflict", "attack", "commodity", "export", "ban",
}

DEFAULT_REGION_EXPOSURE_BY_SECTOR = {
    "Energy": {"Middle East", "India"},
    "IT": {"US", "Europe", "India"},
    "Auto": {"India", "Europe"},
    "Banking": {"India"},
    "Finance": {"India"},
    "Pharma": {"US", "Europe", "India"},
    "FMCG": {"India"},
    "Infra": {"India"},
    "Telecom": {"India"},
    "Metals": {"China", "India"},
    "Real Estate": {"India"},
    "Tech/Internet": {"India", "US"},
    "Index": {"India"},
}

SYMBOL_REGION_OVERRIDES = {
    "RELIANCE": {"Middle East", "India"},
    "ONGC": {"Middle East", "India"},
    "TCS": {"US", "Europe", "India"},
    "INFY": {"US", "Europe", "India"},
    "SUNPHARMA": {"US", "India"},
    "TATAMOTORS": {"Europe", "India"},
    "COFORGE": {"US", "Europe", "India"},
}

LIVE_NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=NSE%20India%20stocks%20when%3A7d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "https://news.google.com/rss/search?q=RBI%20Indian%20markets%20when%3A7d&hl=en-IN&gl=IN&ceid=IN%3Aen",
    "https://news.google.com/rss/search?q=crude%20oil%20India%20markets%20when%3A7d&hl=en-IN&gl=IN&ceid=IN%3Aen",
]
NEWS_CACHE_TTL_SECONDS = 300
_news_cache_articles: list["NewsArticle"] = []
_news_cache_generated_at: datetime | None = None


@dataclass(frozen=True)
class NewsArticle:
    headline: str
    summary: str
    published_at: datetime
    source: str
    url: str | None = None


@dataclass(frozen=True)
class ArticleSemantics:
    headline: str
    summary: str
    source: str
    published_at: str
    involved_regions: list[str]
    affected_sectors: list[str]
    sentiment_score: float
    impact_score: float
    explanation: str
    url: str | None = None


@dataclass(frozen=True)
class StockNewsSignal:
    news_risk_score: float
    news_opportunity_score: float
    news_sentiment: float
    news_impact: float
    news_explanation: str


@dataclass(frozen=True)
class MarketNewsContext:
    generated_at: str
    articles: list[ArticleSemantics]
    sector_sentiment: dict[str, float]
    overall_market_sentiment: float
    top_event_summary: str


def fetch_recent_news() -> list[NewsArticle]:
    global _news_cache_articles, _news_cache_generated_at

    if _news_cache_generated_at is not None:
        cache_age = (datetime.now(timezone.utc) - _news_cache_generated_at).total_seconds()
        if cache_age < NEWS_CACHE_TTL_SECONDS and _news_cache_articles:
            return _news_cache_articles

    live_articles = fetch_live_news()
    if live_articles:
        _news_cache_articles = live_articles
        _news_cache_generated_at = datetime.now(timezone.utc)
        return live_articles

    now = datetime.now(timezone.utc)
    fallback_articles = [
        NewsArticle(
            headline="Middle East tensions keep crude elevated; Indian refiners watch margins",
            summary="Persistent conflict in the Middle East is keeping crude prices firm and raising input-cost pressure for downstream oil marketing companies in India.",
            published_at=now,
            source="LocalFallback",
        ),
        NewsArticle(
            headline="RBI signals stable liquidity stance as domestic credit demand stays resilient",
            summary="A steady RBI tone and resilient domestic loan demand are constructive for Indian banks and diversified financials.",
            published_at=now,
            source="LocalFallback",
        ),
        NewsArticle(
            headline="European auto demand softens while EV component orders stay mixed",
            summary="Soft exports to Europe weigh on select automakers, though EV software suppliers continue to see niche order momentum.",
            published_at=now,
            source="LocalFallback",
        ),
        NewsArticle(
            headline="US enterprise tech budgets stabilize, helping Indian IT deal pipelines",
            summary="Large outsourcing renewals and cloud modernization demand are improving sentiment for export-oriented Indian IT services firms.",
            published_at=now,
            source="LocalFallback",
        ),
        NewsArticle(
            headline="FDA observations on a few global plants keep pharma compliance in focus",
            summary="Regulatory scrutiny remains a stock-specific risk for Indian pharma exporters despite a broadly healthy demand backdrop.",
            published_at=now,
            source="LocalFallback",
        ),
    ]
    _news_cache_articles = fallback_articles
    _news_cache_generated_at = now
    return fallback_articles


def fetch_live_news() -> list[NewsArticle]:
    seen: set[str] = set()
    collected: list[NewsArticle] = []

    try:
        with httpx.Client(follow_redirects=True, timeout=8.0) as client:
            for feed_url in LIVE_NEWS_FEEDS:
                response = client.get(feed_url, headers={"User-Agent": "NSE-Atlas/1.0"})
                if response.status_code != 200:
                    continue
                collected.extend(parse_rss_feed(response.text, seen))
                if len(collected) >= 18:
                    break
    except Exception:
        return []

    collected.sort(key=lambda article: article.published_at, reverse=True)
    return collected[:15]


def parse_rss_feed(xml_text: str, seen: set[str]) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return articles

    for item in root.findall(".//item"):
        title = clean_news_text(item.findtext("title", default=""))
        link = item.findtext("link")
        description = clean_news_text(item.findtext("description", default=""))
        pub_date_raw = item.findtext("pubDate")
        source = clean_news_text(item.findtext("source", default=""))
        if " - " in title and not source:
            title, source = [part.strip() for part in title.rsplit(" - ", 1)]
        if not source:
            source = "LiveFeed"

        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue

        published_at = parse_rss_datetime(pub_date_raw)
        summary = description or title
        articles.append(
            NewsArticle(
                headline=title,
                summary=summary,
                published_at=published_at,
                source=source,
                url=link,
            )
        )
        seen.add(key)

    return articles


def parse_rss_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def clean_news_text(value: str) -> str:
    text = unescape(value or "").replace("<![CDATA[", "").replace("]]>", "")
    return " ".join(text.split())


def extract_article_semantics(article: NewsArticle) -> ArticleSemantics:
    text = f"{article.headline}. {article.summary}".lower()
    involved_regions = [
        region for region, keywords in REGION_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    affected_sectors = [
        sector for sector, keywords in SECTOR_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    if not affected_sectors:
        affected_sectors = ["Index"]
    if not involved_regions:
        involved_regions = ["India"]

    positive_hits = sum(1 for keyword in POSITIVE_KEYWORDS if keyword in text)
    negative_hits = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword in text)
    raw_sentiment = (positive_hits - negative_hits) / max(positive_hits + negative_hits, 1)
    sentiment_score = max(-1.0, min(1.0, raw_sentiment))

    impact_hits = sum(1 for keyword in HIGH_IMPACT_KEYWORDS if keyword in text)
    region_lift = 0.8 * max(len(involved_regions) - 1, 0)
    sector_lift = 0.6 * max(len(affected_sectors) - 1, 0)
    impact_score = min(10.0, round(2.5 + (impact_hits * 1.6) + region_lift + sector_lift, 2))
    explanation = article.summary.strip() or article.headline.strip()

    return ArticleSemantics(
        headline=article.headline,
        summary=article.summary,
        source=article.source,
        published_at=article.published_at.isoformat(),
        involved_regions=involved_regions,
        affected_sectors=affected_sectors,
        sentiment_score=round(sentiment_score, 3),
        impact_score=impact_score,
        explanation=explanation,
        url=article.url,
    )


def build_market_news_context() -> MarketNewsContext:
    articles = [extract_article_semantics(article) for article in fetch_recent_news()]
    sector_values: dict[str, list[float]] = {}
    for article in articles:
        weighted = article.sentiment_score * (article.impact_score / 10.0)
        for sector in article.affected_sectors:
            sector_values.setdefault(normalize_sector_code(sector), []).append(weighted)

    sector_sentiment = {
        sector: round(mean(values), 3)
        for sector, values in sector_values.items()
        if values
    }
    overall_market_sentiment = round(mean(sector_sentiment.values()), 3) if sector_sentiment else 0.0
    top_event = max(
        articles,
        key=lambda article: (article.impact_score, abs(article.sentiment_score)),
        default=None,
    )
    top_event_summary = top_event.explanation if top_event else "No recent news events were available."
    return MarketNewsContext(
        generated_at=datetime.now(timezone.utc).isoformat(),
        articles=articles,
        sector_sentiment=sector_sentiment,
        overall_market_sentiment=overall_market_sentiment,
        top_event_summary=top_event_summary,
    )


def compute_stock_news_signals(
    snapshots: Iterable[object],
    mandate: UserMandate,
) -> dict[str, StockNewsSignal]:
    market_news = build_market_news_context()
    mandate_inclusions = {normalize_sector_code(value) for value in mandate.sector_inclusions}
    signals: dict[str, StockNewsSignal] = {}

    for snapshot in snapshots:
        symbol = getattr(snapshot, "symbol")
        sector = normalize_sector_code(getattr(snapshot, "sector", "Unknown"))
        regions = set(SYMBOL_REGION_OVERRIDES.get(symbol, DEFAULT_REGION_EXPOSURE_BY_SECTOR.get(sector, {"India"})))

        risk_score = 0.0
        opportunity_score = 0.0
        sentiment_values: list[float] = []
        impact_values: list[float] = []
        reasons: list[str] = []

        for article in market_news.articles:
            sector_match = sector in {normalize_sector_code(item) for item in article.affected_sectors}
            region_match = bool(regions.intersection(article.involved_regions))
            if not sector_match and not region_match and "Index" not in article.affected_sectors:
                continue

            exposure_multiplier = 1.0 + (0.2 if sector_match and region_match else 0.0)
            mandate_multiplier = 1.15 if sector in mandate_inclusions else 1.0
            normalized_impact = article.impact_score / 10.0
            signed_effect = article.sentiment_score * normalized_impact * exposure_multiplier * mandate_multiplier

            if signed_effect < 0:
                risk_score += abs(signed_effect)
            else:
                opportunity_score += signed_effect
            sentiment_values.append(article.sentiment_score)
            impact_values.append(article.impact_score)
            if len(reasons) < 2:
                reasons.append(article.explanation)

        signals[symbol] = StockNewsSignal(
            news_risk_score=round(min(1.0, risk_score), 4),
            news_opportunity_score=round(min(1.0, opportunity_score), 4),
            news_sentiment=round(mean(sentiment_values), 4) if sentiment_values else 0.0,
            news_impact=round(max(impact_values), 4) if impact_values else 0.0,
            news_explanation=" ".join(reasons) if reasons else "No recent material news mapped to this stock.",
        )

    return signals
