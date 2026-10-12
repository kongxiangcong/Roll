"""One M0 design proposed from coverage metadata, never from held-out outcomes."""
import hashlib
import json
from pathlib import Path
from roll.accounts.ledger import encode


def proposal(dataset):
    references=json.loads((Path(__file__).parent/'reference/sources.json').read_text(encoding='utf-8'))
    for source in references:
        if source.get('http_status')==200:
            actual=Path(__file__).parent/'reference'/source['file']
            if hashlib.sha256(actual.read_bytes()).hexdigest()!=source['sha256']:raise RuntimeError('研究费用原依据SHA损坏')
    sealed=dataset['partitions']['SEALED'];calibration=dataset['partitions']['CALIBRATION']
    mature=max(0,sealed['rows']-20)
    design={'design_version':'17-m0-v1','hypothesis':'A fixed transparent daily price-volume candidate improves fee-after return under matched risk/exposure; not best retrospective stock selection',
        'horizon_sessions':20,'event':'Positive RAW realized20-session round-trip net return under frozen execution and known company-action treatment; unresolved action/status yields unscorable/interval cases, never zero',
        'candidates':[{'candidate_id':'PRICE_VOLUME_LOGIT_V1','status':'DESIGN_ONLY_NOT_MODEL_FROZEN',
            'features':['raw_return_5','raw_return_20','raw_return_volatility_20','log_volume_to_trailing20_mean'],
            'fitting':'L2 logistic regression; standardization fitted only DEVELOPMENT; lambda=1; no prompt or manual stock selection',
            'calibration':'Intercept-only held-out probability calibration; no fitting on SEALED; exact implementation and fingerprint ticket19',
            'threshold':'0.60','model_artifact_fingerprint':None,'calibrator_artifact_fingerprint':None}],
        'primary_objective':{'metric':'Paired20-session fee-after NAV return improvement over every preregistered comparable baseline',
            'minimum_improvement_nav_return':'0.0025','confidence_rule':'One-sided95% lower bound >0.0025 at single final point; all required comparisons/gates must hold',
            'risk_constraints':{'maximum_simulated_gross_exposure':'0.50','maximum_drawdown':'0.10',
                'candidate_drawdown_excess_over_risk_matched_baseline':'0.02','minimum_decision_coverage':'0.20'},
            'basis':'Research choice before outcome computation. Assumed3bp commission each side +5bp sell stamp +0.1bp transfer each side +5bp slippage each side =21.2bp trade cost; at50% exposure10.6bp NAV. Twice this rounded upward to25bp is a meaningful NAV improvement hurdle, not estimated alpha or actual broker cost.'},
        'baselines':[{'id':'CASH','policy':'same synthetic initial capital, no interest assumed; display actual zero exposure separately'},
            {'id':'START_HOLD','policy':'same start, budget/lot/rules,50% initial allowed exposure, no resets, comparable fees'},
            {'id':'MA5_MA20','policy':'fixed5/20-day moving-average crossover,50% maximum exposure, same execution/cost/rules; no tuning'}],
        'windows':dataset['partitions'],'label_isolation':{'lookback_sessions':20,'horizon_sessions':20,'embargo_sessions':20,
            'rule':'A fitted label must mature inside its allowed DEVELOPMENT/CALIBRATION window; boundary-spanning labels purged. Calibration receives preceding20 rows only as past feature context; no random same-day split.'},
        'statistics':{'method':'Paired calendar-date moving-block bootstrap, block length20 sessions; same-day securities jointly resampled; seed1701,2000 replicates',
            'dependency_sensitivity_block_sessions':[20,40],'minimum_effective_time_blocks':30,
            'minimum_calibration_examples_per_class':20,'minimum_selected_mature_examples':40,
            'probability_checks':['Brier/log loss against development base rate and transparent rule','fixed5 equal-width reliability bins,20 mature cases per occupied bin','ROC discrimination and selected-subset support, no probability reliability claim from lower Brier alone'],
            'pass_look_count':1,'alpha':'0.05','multiple_comparison_policy':'Intersection-union: every preregistered required baseline and gate must pass; no choosing favorable comparison. Sensitivity does not create another PASS look.',
            'validity':'Stationarity/weak-dependence assumptions and finite-sample coverage must be automatically validated and technically reviewed in20.30 blocks is a conservative design eligibility condition, not a universal bootstrap theorem; inadequate support or failed assumptions=>INCONCLUSIVE, never lower cutoff after seeing sealed.',
            'reference':'Kunsch(1989), The jackknife and the bootstrap for general stationary observations, Ann.Statist.17:1217–1241; author bibliography https://people.math.ethz.ch/~hkuensch/papers/'},
        'support_projection':{'metadata_only':True,'sealed_mature_label_upper_bound':mature,
            'calibration_mature_label_upper_bound':max(0,calibration['rows']-20),
            'sealed_nonoverlap20_block_upper_bound':mature//20,
            'state':'INSUFFICIENT_FOR_CONFIRMATORY_PASS' if mature//20<30 else 'SUPPORT_ASSUMPTIONS_STILL_REQUIRE_VALIDATION',
            'historical_final_independence':'UNPROVEN; engineering archive exposure is recorded, no strategy results examined'},
        'costs':{'version':'17-cost-v1','currency':'CNY','broker_actual_commission':'UNKNOWN',
            'commission_scenario_rate':'0.0003','minimum_commission_yuan':'5','commission_includes_regulatory_fees':True,
            'extra_regulatory_charge':'0','stamp_sell_rate':'0.0005','transfer_each_side_rate':'0.00001',
            'slippage_each_side_rate':'0.0005','rounding':'Decimal to yuan cents at fee boundary; retain underlying raw precision',
            'evidence':references,'effective_scope':'SSE MAIN ordinary A-share study scenario. Official pages currently displayed; 2023-08-28 stamp reduction separately archived. Exact broker tariff and continuous historical stability remain unproven; not official account expense facts.',
            'unknown_policy':'Unknown actual fee never becomes0; use explicit scenario intervals in research and retain formal cost-input restriction.'},
        'execution':{'scale':'DAILY_ONLY_NO_INTRADAY_TOUCH_ORDER_INFERENCE','base_delay':'NEXT_OPEN',
            'price_window':'Use next declared daily OHLC and explicit exchange rule limit; orders outside frozen permissible price band do not fill',
            'quantity':'100-share ordinary SSE MAIN lot, Decimal cash/fees and T+1 available shares; no leverage',
            'synthetic_initial_cash_yuan':'1000000','synthetic_initial_positions':[],
            'synthetic_basis':'Research simulation scale chosen to allow at least one100-share600519 lot under50% exposure at publicly reported1258.62 quote; not user funds/baseline/authorization or research runtime money budget',
            'partial_or_missed':'0/50/100% execution stress, retain all rejected opportunities; no fill does not label prediction loss',
            'missing_or_unknown':'No imputation/no selective deletion: explicit inability-to-trade/unknown-status intervals and missing rows, report sensitivity; uncertain action treatment or label cannot be scored',
            'maturity':'After20 trading sessions or preregistered deterministic terminal settlement; unconfirmed settlement unresolved. At deadline unmatured labels separately listed, never scored/learned.',
            'coverage':'Only actually archived checkpoints; later price supplementation cannot backfill an unarchived forecast'},
        'g5':{'time_segments':'Report each chronological third of the eligible historical test and forward mature window, same targets; each insufficient segment remains INCONCLUSIVE',
            'commission_rates':['0.0003','0.0006','0.003'],'slippage_each_side_rates':['0.0005','0.001','0.002'],
            'delays':['NEXT_OPEN','NEXT_CLOSE','ONE_MORE_SESSION_OPEN','OUTSIDE_ALLOWED_PRICE_NO_FILL'],
            'parameter_neighborhood':{'penalty':['0.5','1','2'],'lookback_sessions':[15,20,25],'probability_threshold':['0.55','0.60','0.65'],
                'evaluation':'One-at-a-time neighbors around fixed primary, never choose a neighbor winner; each fit/candidate/threshold attempt persisted'},
            'required':'Base improvement>=25bp NAV with preregistered interval/risk/support; stressed net value must not reverse below comparable baseline, risk bounds hold. Insufficient stress support is INCONCLUSIVE; failure cannot be repaired by shrinking old scope.',
            'migration_scope':dataset['scope'],'unknown_scope':'Other names/boards/markets are monitoring only; extension needs linked new experiment and unused evidence'},
        'formal_monitoring':{'scope':dataset['scope'],'checkpoints':{'operations':'Every actual running post-market checkpoint; missing days retained','statistics':'At registered30-session mature-results review and qualification expiry; no extra confirmation PASS look'},
            'execution':'Compare actual next-open/next-close delays, missing/partial fills, quote-vs-fill, realized fees with frozen scenarios; outside declared delay/price/cost bounds immediately restrict affected ability without declaring statistical FAIL',
            'drift':'Fit feature1st/99th percentiles on DEVELOPMENT only; if >=20% of latest20 eligible observations outside fixed reference or required-input coverage<80%, restrict use pending review. Operational sentinel, not a causal or statistical profitability verdict.',
            'mature_results':'Report fixed mature probability/utility/support checks at registered review; insufficient evidence=>INCONCLUSIVE, no adjusting cutoffs on new losses',
            'unmatured_results_scored':False,'policy_change':'Reason+new fingerprint+successor protocol, preserve previous verdict and visits; no silent threshold changes'},
        'stopping':{'timezone':'Asia/Shanghai','maximum_natural_months':3,'calendar_month_rule':'Local wall time; month addition clamps to destination month end; inclusive final cutoff, no90-day substitution',
            'forward_origin':'First successfully persisted actual frozen-model future prediction in30/32; protocol registration/deployment/historical replay/synthetic account do not start it',
            'pass_checkpoint':'ONE_FINAL_CONFIRMATORY_POINT_AT_DEADLINE_OR_PREREGISTERED_HARD_STOP',
            'early_stops':['hard safety/input/version failure','technical model fit/call/deadline limit','user stops ability; statistical verdict separately preserved'],
            'no_extension':'Absence/backend switching/unfavorable results/maturity deficits never extend original deadline; successor requires new information value',
            'technical_limits':{'maximum_primary_candidates':1,'maximum_model_fits_including_fixed_neighbors':5,'maximum_fit_seconds':60,'maximum_calibration_fits':1,'sealed_parameter_tuning_calls':0,'runtime_money_budget_required':False}},
        'risk_policy_evidence':{'owner':'ticket22','inherits_profit_model_pass':False,
            'required':['own frozen deterministic rules/data fingerprints','authorized risk boundaries','calculation and stress-execution proof','online consistency and scope checks'],'profit_model_required_gates':['G1','G2','G3','G4','G5','G6','G7']}}
    if dataset.get('data_use')=='RECONSTRUCTED_RESEARCH':
        from roll.research.reconstruction import CANDIDATE,FEATURES
        design['design_version']='19-m0-reconstructed-v2'
        design['event']='Positive20-session single RAW round-trip economic return after historical statutory costs, frozen broker/slippage scenario and source-bound cash rights/tax; unresolved cases are not losses'
        design['candidates'][0].update(candidate_id=CANDIDATE,features=FEATURES,
            status='PREREGISTERED_RECONSTRUCTED_CANDIDATE',feature_basis='Gross cash economic return chain from effective events on/before observation only; not current qfq')
        design['research_assumptions']=dataset['research_assumptions']
        design['data_use']='RECONSTRUCTED_RESEARCH'
        design['support_projection']['state']='FIT_SUPPORT_TO_BE_COMPUTED; CONFIRMATORY_INDEPENDENCE_NOT_ESTABLISHED'
        design['execution']['synthetic_basis']='Frozen research lot capital, not actual account funds or continuous NAV'
        design['statistics']['fit_support']='Both DEV classes present; CAL at least20 per class. Effective blocks/bins/selected thresholds remain later validation conditions.'
    elif dataset.get('source_origin')=='HOST_DATA_REQUEST':
        design['execution']['synthetic_basis']='Research simulation capital only; no user funds or prior engineering stock-price authority. Real windows remain NOT_PREREGISTERED.'
        design['support_projection']['state']='RESEARCH_WINDOWS_NOT_PREREGISTERED'
    design['design_fingerprint']=hashlib.sha256(encode(design).encode()).hexdigest()
    return design
