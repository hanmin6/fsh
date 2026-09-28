# Plan

Create an offline static entry under `ui-showcase/` using the checked-in `client/custom/src/fusanhe/ui-runtime.js` and `client/custom/res/fusanhe/ui.css`. A narrow mock HostBridge supplies fixed fictional records and intercepts links. This preserves the original React implementation while letting reviewers inspect it without EspoCRM.

The showcase shell owns only navigation and screen descriptions. Native EspoCRM and Android screens appear in inventories with source links because their runtime hosts are unavailable in a browser-only static preview. No PHP, API, database or generated UI bundle changes are required.

**Constitution check:** Use fictional data; fail closed on outbound actions; block all mutating HostBridge calls; state preview limits clearly. No migration. Remove `ui-showcase/` and this spec to roll back. Verify with JavaScript syntax checks, local HTTP, browser navigation of representative screens, and network/error inspection.
