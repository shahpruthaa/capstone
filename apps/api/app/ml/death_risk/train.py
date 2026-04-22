from __future__ import annotations
import json, pickle, logging
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.daily_bar import DailyBar
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

def build_death_risk_dataset(db, min_days_threshold=200):
    stock_stats = db.execute(
        select(
            Instrument.symbol,
            func.count(DailyBar.id).label('n_days'),
            func.min(DailyBar.close_price).label('min_close'),
            func.max(DailyBar.close_price).label('max_close'),
            func.avg(DailyBar.close_price).label('avg_close'),
            func.stddev(DailyBar.close_price).label('std_close'),
            func.avg(DailyBar.total_traded_qty).label('avg_volume'),
        )
        .join(Instrument, DailyBar.instrument_id == Instrument.id)
        .where(Instrument.series == 'EQ')
        .group_by(Instrument.symbol)
    ).all()
    rows = []
    for s in stock_stats:
        if not s.avg_close or float(s.avg_close) <= 0:
            continue
        avg_close = float(s.avg_close)
        std_close = float(s.std_close) if s.std_close else 0.0
        min_close = float(s.min_close)
        max_close = float(s.max_close)
        avg_vol = float(s.avg_volume) if s.avg_volume else 0.0
        cv = std_close / avg_close if avg_close > 0 else 0.0
        max_dd = (max_close - min_close) / max_close if max_close > 0 else 0.0
        price_collapse = 1.0 if max_close > 0 and (min_close / max_close) < 0.3 else 0.0
        low_liq = 1.0 if avg_vol < 1000 else 0.0
        label = 1 if s.n_days < min_days_threshold else 0
        rows.append({
            'symbol': s.symbol, 'n_days': s.n_days, 'cv_price': cv,
            'max_drawdown': max_dd, 'price_collapse': price_collapse,
            'low_liquidity': low_liq, 'avg_volume_log': float(np.log1p(avg_vol)),
            'label': label,
        })
    df = pd.DataFrame(rows)
    n_dead = int(df['label'].sum())
    logger.info(f'Dataset: {len(df)} stocks, {n_dead} dead, {len(df)-n_dead} alive')
    return df

def train_death_risk_classifier(df):
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    feature_cols = ['cv_price', 'max_drawdown', 'price_collapse', 'low_liquidity', 'avg_volume_log']
    X = df[feature_cols].values
    y = df['label'].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
    cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring='roc_auc')
    logger.info(f'CV AUC: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}')
    model.fit(X_scaled, y)
    importances = dict(zip(feature_cols, model.feature_importances_))
    logger.info(f'Importances: {importances}')
    return {'model': model, 'scaler': scaler, 'feature_cols': feature_cols,
            'cv_auc': float(cv_scores.mean()), 'cv_auc_std': float(cv_scores.std()),
            'train_accuracy': float(model.score(X_scaled, y)),
            'dataset_rows': int(len(df)), 'positive_labels': int(y.sum()),
            'negative_labels': int(len(y) - int(y.sum()))}

def save_death_risk_artifacts(result, artifact_dir):
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with (artifact_dir / 'death_risk_model.pkl').open('wb') as f:
        pickle.dump(result['model'], f)
    with (artifact_dir / 'death_risk_scaler.pkl').open('wb') as f:
        pickle.dump(result['scaler'], f)
    metrics = {'cv_auc': result['cv_auc'], 'cv_auc_std': result['cv_auc_std'],
               'train_accuracy': result['train_accuracy'], 'feature_cols': result['feature_cols']}
    with (artifact_dir / 'death_risk_metrics.json').open('w') as f:
        json.dump(metrics, f, indent=2)
    metadata = {
        'model_version': artifact_dir.name,
        'training_mode': 'research',
        'target_variable_definition': 'Binary proxy label set to 1 when a symbol has fewer than 200 trading-history days in the local database snapshot; 0 otherwise.',
        'training_methodology': 'GradientBoostingClassifier over summary price and liquidity features with 5-fold cross-validation.',
        'validation_methodology': '5-fold cross-validation ROC AUC on the training snapshot only. No explicit out-of-sample time-series validation is currently available.',
        'validation_summary': {
            'cv_auc': result['cv_auc'],
            'cv_auc_std': result['cv_auc_std'],
            'train_accuracy': result['train_accuracy'],
        },
        'dataset_summary': {
            'rows': result['dataset_rows'],
            'positive_labels': result['positive_labels'],
            'negative_labels': result['negative_labels'],
        },
        'limitations': [
            'The target is a survivorship/listing-history proxy rather than a realized default, delisting, or permanent capital-impairment label.',
            'The model has no documented out-of-sample time-series validation and should not be used as a production gating signal yet.',
            'Feature set is intentionally narrow and should be treated as a coarse liquidity/stability heuristic.',
        ],
        'production_readiness': 'not_ready',
    }
    with (artifact_dir / 'death_risk_metadata.json').open('w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    logger.info(f'Saved to {artifact_dir}')

def predict_death_risk(symbols, db, artifact_dir):
    artifact_dir = Path(artifact_dir)
    model_path = artifact_dir / 'death_risk_model.pkl'
    if not model_path.exists():
        return {s: 0.0 for s in symbols}
    with model_path.open('rb') as f:
        model = pickle.load(f)
    with (artifact_dir / 'death_risk_scaler.pkl').open('rb') as f:
        scaler = pickle.load(f)
    stock_stats = db.execute(
        select(Instrument.symbol,
            func.count(DailyBar.id).label('n_days'),
            func.min(DailyBar.close_price).label('min_close'),
            func.max(DailyBar.close_price).label('max_close'),
            func.avg(DailyBar.close_price).label('avg_close'),
            func.stddev(DailyBar.close_price).label('std_close'),
            func.avg(DailyBar.total_traded_qty).label('avg_volume'))
        .join(Instrument, DailyBar.instrument_id == Instrument.id)
        .where(Instrument.symbol.in_(symbols))
        .group_by(Instrument.symbol)
    ).all()
    results = {}
    for s in stock_stats:
        if not s.avg_close or float(s.avg_close) <= 0:
            results[s.symbol] = 0.0
            continue
        avg_close = float(s.avg_close)
        std_close = float(s.std_close) if s.std_close else 0.0
        min_close = float(s.min_close)
        max_close = float(s.max_close)
        avg_vol = float(s.avg_volume) if s.avg_volume else 0.0
        features = np.array([[
            std_close / avg_close if avg_close > 0 else 0.0,
            (max_close - min_close) / max_close if max_close > 0 else 0.0,
            1.0 if max_close > 0 and (min_close / max_close) < 0.3 else 0.0,
            1.0 if avg_vol < 1000 else 0.0,
            float(np.log1p(avg_vol)),
        ]])
        X_scaled = scaler.transform(features)
        results[s.symbol] = float(model.predict_proba(X_scaled)[0][1])
    for sym in symbols:
        if sym not in results:
            results[sym] = 0.0
    return results
