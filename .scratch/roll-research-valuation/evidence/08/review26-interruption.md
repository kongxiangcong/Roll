# review26 sandbox interruption

The isolated no-model test run stalled at `test_registered_collector_empty...` for over four minutes; last tmp-directory modification07:42:58 Asia/Shanghai, inspection07:47:40. Original log remained empty due captured stdout buffering. No actual model/service/network test was requested.

Read-only CIM verified exact pytest PIDs13136(wrapper)/40736(child), both command lines included `--basetemp D:/dsh-proj/Roll/.scratch/rv08-review26`. Only verified child40736 was explicitly stopped; wrapper13136 then exited on its own before the next identity check, so the script safely reported ownership mismatch rather than terminating anything else. All temporary data/logs retained. Other original8010/5173 and07 services unaffected.

This is not recorded as a passing test or proven production defect. The prior session has known sandbox socket/async child restrictions; the same five public behavior tests are rerun escalated with a30-second faulthandler diagnostic to distinguish environment from product behavior. No real CODEX/auth is involved.
