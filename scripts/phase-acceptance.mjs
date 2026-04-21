import fs from 'node:fs/promises';
import path from 'node:path';

const apiBaseUrl = 'http://127.0.0.1:8000';
const repoRoot = process.cwd();

async function fetchJson(endpoint) {
  const response = await fetch(`${apiBaseUrl}${endpoint}`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${endpoint} returned ${response.status}: ${body}`);
  }
  return response.json();
}

async function exists(relativePath) {
  try {
    await fs.access(path.resolve(repoRoot, relativePath));
    return true;
  } catch {
    return false;
  }
}

function assert(condition, message, failures) {
  if (!condition) {
    failures.push(message);
  }
}

async function run() {
  const failures = [];

  const health = await fetchJson('/healthz');
  const currentModel = await fetchJson('/api/v1/models/current');
  const marketData = await fetchJson('/api/v1/market-data/summary');
  const benchmark = await fetchJson('/api/v1/benchmarks/summary');
  const observability = await fetchJson('/api/v1/observability/kpis');

  const smokeScriptExists = await exists('scripts/ui-smoke-playwright.mjs');
  const packageJson = JSON.parse(await fs.readFile(path.resolve(repoRoot, 'package.json'), 'utf-8'));
  const packageScripts = packageJson?.scripts ?? {};
  const hasBuildAndLintScripts = Boolean(packageScripts.build && packageScripts.lint);

  const benchmarkStrategies = Array.isArray(benchmark.strategies) ? benchmark.strategies : [];
  const benchmarkWithFidelity = benchmarkStrategies.filter((strategy) => strategy.source_type && strategy.relative_accuracy_score_pct !== undefined && strategy.relative_accuracy_score_pct !== null);

  assert(health.status === 'ok', 'Phase 0: health endpoint is not ok.', failures);
  assert(Boolean(currentModel) && typeof currentModel.available === 'boolean', 'Phase 0: model runtime endpoint did not return the expected contract.', failures);
  assert(typeof marketData.daily_bar_count === 'number', 'Phase 0: market data summary is missing the bar-count contract.', failures);
  assert(Boolean(observability.phase_gates?.phase_0_data_contracts), 'Phase 0: observability gate is not green.', failures);

  assert(benchmarkStrategies.length > 0, 'Phase 1: benchmark summary returned no strategies.', failures);
  assert(benchmarkWithFidelity.length > 0, 'Phase 1: benchmark fidelity metadata is missing from strategy rows.', failures);
  assert(Boolean(observability.phase_gates?.phase_1_benchmark_fidelity), 'Phase 1: observability gate is not green.', failures);

  assert(smokeScriptExists && hasBuildAndLintScripts, 'Phase 2: the local test harness is incomplete.', failures);
  assert(Boolean(observability.phase_gates?.phase_2_test_harness), 'Phase 2: observability gate is not green.', failures);

  assert(Boolean(observability.phase_gates?.phase_3_engineering_health), 'Phase 3: engineering-health baseline is not green.', failures);
  assert(typeof observability.engineering_health?.sample_window === 'string', 'Phase 3: engineering-health contract is missing.', failures);

  assert(Boolean(observability.phase_gates?.phase_4_stable_baseline), 'Phase 4: stable-baseline gate is not green.', failures);
  assert(
    observability.reliability?.generate_error_rate_pct === 0 && observability.reliability?.benchmark_error_rate_pct === 0,
    'Phase 4: reliability baseline still reports errors.',
    failures,
  );

  const report = {
    phase0: {
      status: 'pass',
      health: health.status,
      available: currentModel.available,
      dailyBarCount: marketData.daily_bar_count,
      gate: observability.phase_gates?.phase_0_data_contracts,
    },
    phase1: {
      status: 'pass',
      strategies: benchmarkStrategies.length,
      fidelityRows: benchmarkWithFidelity.length,
      gate: observability.phase_gates?.phase_1_benchmark_fidelity,
    },
    phase2: {
      status: 'pass',
      smokeScriptExists,
      hasBuildAndLintScripts,
      gate: observability.phase_gates?.phase_2_test_harness,
    },
    phase3: {
      status: 'pass',
      gate: observability.phase_gates?.phase_3_engineering_health,
      sampleWindow: observability.engineering_health?.sample_window,
    },
    phase4: {
      status: 'pass',
      gate: observability.phase_gates?.phase_4_stable_baseline,
      generateErrorRatePct: observability.reliability?.generate_error_rate_pct,
      benchmarkErrorRatePct: observability.reliability?.benchmark_error_rate_pct,
    },
  };

  if (failures.length > 0) {
    console.error(JSON.stringify(report, null, 2));
    throw new Error(failures.join('\n'));
  }

  console.log(JSON.stringify(report, null, 2));
}

run().catch((error) => {
  console.error('PHASE_ACCEPTANCE_FAILED');
  console.error(error?.stack || String(error));
  process.exit(1);
});
