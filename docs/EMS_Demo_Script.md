# EMS demo script (about 10 minutes) - updated for B11

Before you start: backend and frontend running, browser on http://localhost:5173, one private window per role (or log out between roles).
Passwords: use the demo cards on the login page.

## 1. Site Engineer (data entry)
1. Dashboard: fleet size, **availability as "x of y units available"**, service due, fuel for the latest 30 days (litres; electricity is shown separately in kWh), recent incidents.
2. Equipment: the ID fills itself in (next free number). Each machine has a capacity **with its unit** (tonnes, m3, kW or litres). Fuel Type lets you pick an existing type or type a new one; a type without a price shows a warning. Below the form: latest 10 entries and "View all records".
3. Fuel Logs: pick equipment from the list, project fills itself in. The label shows the unit for that machine (litres for diesel/petrol, kWh for electric). The cost is calculated from the fuel rate (SAR).
   - Try a wrong date: a date in the future, or before the machine arrived at its current project, is refused with a clear message ("... Entry not added.").
4. Utilization Log: equipment dropdown; operating hours are a period total (the sample data is one weekly total per machine), up to 168. Same date checks as fuel.
5. Incidents: "Incident Time (approx.)".
6. Transfers: choose a machine (machines that already have a pending request or are decommissioned are greyed out and say why). To Project, optional reason, Submit.
7. Information: search "eq-7" or "crane" or a project name; open a profile (capacity shows its unit); open a project and its equipment.

## 2. Workshop Mechanic
1. Dashboard: unresolved breakdowns ("Awaiting repair" / "Under repair"), downtime, services due.
2. Breakdowns: Status is a dropdown (Open / Under Repair / Resolved). Log one: **the machine's status becomes Under Repair by itself** (check the Fleet status panel / availability on a dashboard).
3. Repairs: log a repair for that breakdown. It turns Resolved by itself, and **the machine goes back to Active** when it has no other unresolved breakdown.
4. Maintenance History: pick the machine - services, breakdowns and repairs on one timeline, with a date filter.

## 3. Fleet Manager
1. Dashboard: pending approvals count (also shown as the sidebar badge).
2. Transfer Approval: click a row to see equipment condition (breakdowns, service, last 30 days of use) and both projects. Approve one: the machine moves and the badge drops. Reject one: a reason is required.
   - "Out of date" rows (machine already moved elsewhere) can only be rejected.
3. Operational & Maintenance: per-project units, hours, fuel (litres and kWh separately), overdue services, 90-day costs.
4. Reports: pick a register, search/filter, download CSV or PDF.
5. Employees (sidebar): new self-registered accounts wait here as Inactive; the number waiting is shown next to the menu item. Set one to Active to let that person sign in.
6. Fuel Rates: the price per unit (per litre; per kWh for electricity). Predictive Maintenance and Fuel Forecast say "Coming in Phase 3" and explain what they will do.

## What to say about security
- Login with a token (8 hours); a new account stays Inactive until a Fleet Manager activates it.
- Roles are enforced on the server, not only in the menus: a Site Engineer cannot approve a transfer or edit fuel rates even by calling the API directly.
- Requested By / Approved By come from the logged-in person. Nobody approves their own request.

## Honest limits (say them before you are asked)
- "Latest entries" means newest, not "entered by me" (no created-by column yet).
- Employees are not tied to a project, so any engineer can request a transfer for any machine.
- No "cancel my request" yet and no email notifications.
- Login is our own (token + EMPLOYEE table). Supabase/SSO would be a later upgrade.
- Fuel/usage demo data is synthetic where marked; Phase 3 (ML) is next.
- Capacity in the sample data is in tonnes for every machine type (a convention for the generated data); real units would come from the real fleet register.
- When a repair finishes, a machine that was Idle before the breakdown returns to Active (the system does not remember it was Idle).
- Date checks apply to new entries and changed dates; the generated history is not re-checked.
- A machine's fuel unit comes from its fuel type: litres for diesel/petrol, kWh for electric, "units" for anything else.
