# Draft content for RACK-210 (stands in for the text an AI model writes from the gathered evidence)

## Release notes
### Highlights
Rack and cabinet records now show their ports and the cables between them.
### New in this release
Rack and cabinet records in Rack Manager now include a {Ports tab label} tab and a {Cabling tab label} tab, so operators can see every port on the equipment placed in the record and review the cables connected to those ports without leaving the page. The {Cabling tab label} tab also lets you change the cable type.
### UI changes
Two new tabs appear on rack and cabinet records: {Ports tab label} and {Cabling tab label}. The {Cabling tab label} tab includes an {Edit connection action} action on each connection.

## Topic: CONCEPT: Viewing rack and cabinet equipment (UPDATE)
### File
concepts/viewing-rack-and-cabinet-equipment.md
### Why
The feature adds a new part of the rack page, so the existing overview needs to describe it.
### Shortdesc
The {Ports tab label} and {Cabling tab label} tabs on a rack or cabinet show its ports and the cables that connect them.
### Key Benefits
- See the speed and status of every port in a rack or cabinet without opening each device.
- See every cable connected to that equipment in one list.
- Review and change cable types directly from the rack page.
### How it works
A rack or cabinet record has a {Ports tab label} tab and a {Cabling tab label} tab next to its existing tabs.
- The {Ports tab label} tab lists every port on the devices placed in the rack or cabinet, including devices one level down.
- The {Cabling tab label} tab lists every cable where at least one end is a port on that equipment.
[SME NEEDED] Confirm: a device mounted directly in the rack without a slot appears in the list.
Note: the lists look two levels into the rack, so a device inside a chassis is included.
### Considerations
- You can customise which columns each list shows. The Utilisation column is available only when the Advanced plugin is active.
- [SME NEEDED] Confirm: are both tabs visible to every role that can open a rack record?

## Topic: TASK: Check ports on a rack or cabinet (NEW)
### File
tasks/check-ports-on-a-rack-or-cabinet.md
### Why
A separate user flow: open the record, then use the {Ports tab label} tab to audit port speed and status.
### Shortdesc
Check the speed and status of every port on the equipment in a rack or cabinet.
### Prerequisites
- [SME NEEDED, BLOCKER] Role required: confirm the exact name of the role that can open rack records.
### Context
Use the ports tab to find out which interfaces are up, down, or free on the equipment in a rack or cabinet.
### Steps
- Navigate to Rack Manager.
- Open a rack or cabinet record.
- Select the {Ports tab label} tab.
→ Result: the list shows every port on the equipment in the record, with its device, speed, and status.
- Review the device, port and speed of each port.
- Select a device name to open that device.
→ Info: columns can be changed from the list settings.
### Result
You can audit the ports of a whole rack or cabinet from one record.

## Topic: TASK: Review and change cabling on a rack or cabinet (NEW)
### File
tasks/review-and-change-cabling-on-a-rack-or-cabinet.md
### Why
A separate flow for the {Cabling tab label} tab, including changing a cable type.
### Shortdesc
Review the cables on a rack or cabinet and change the cable type of a connection.
### Prerequisites
- [SME NEEDED, BLOCKER] Role required: same as the Ports tab; confirm the exact role name.
### Context
Use this procedure to audit cabling and correct the cable type of a connection.
### Steps
- Open Rack Manager.
- Open a rack or cabinet record.
- Select the {Cabling tab label} tab.
→ Result: the list shows every cable connected to the equipment.
- Select {Edit connection action} on the connection you want to change.
- Choose a cable type: {Cable type options}.
→ Info: only one cable can be connected to a port at a time.
- Save your changes.
### Result
You can audit and update the cabling of a whole rack or cabinet from one record.
### Example
A connection that was recorded as Copper is changed to Fibre after a cable swap; the list then shows Fibre for that connection.

## Release notes detail
### Ports tab on a rack
The {Ports tab label} tab lists every port on the equipment placed in the rack, with its device, speed, and status.
RACK-210 + PR 318 + 2026-10-13 + confirmed on the demo app
### Ports tab on a cabinet
The {Ports tab label} tab lists every port on the equipment placed in the cabinet.
RACK-210 + PR 318 + 2026-10-13 + confirmed on the demo app
### Cabling tab on a rack
The {Cabling tab label} tab lists the cables connected to the rack's equipment and lets you change the cable type.
RACK-210 + PR 321 + 2026-10-13 + confirmed on the demo app
### Cabling tab on a cabinet
The {Cabling tab label} tab lists the cables connected to the cabinet's equipment.
RACK-210 + PR 321 + 2026-10-13 + confirmed on the demo app

## No reference topic
The feature adds no new form fields. The list columns are configurable and are covered in the concept topic.

## Technical detail
### AC Layer 1+2 — Ports on a rack
Relationship rel-0041 (app-rack-core, PR 318) lists the ports of devices placed in the rack, two levels deep. Query capped at 500 rows by property rack.related_list.max_ports.
### AC Layer 3+4 — Ports on a cabinet
Relationship rel-0042 (app-rack-core, PR 318). Identical logic to the rack relationship, applied to the cabinet table.
### AC Layer 5+6 — Cabling on a rack
Relationship rel-0043 (app-rack-core, PR 321). Matches a connection when either end is a port on the rack's equipment.
### AC Layer 7 — Cabling on a cabinet
Relationship rel-0044 (app-rack-core, PR 321). Identical cabling logic applied to the cabinet table.
### Advanced plugin variant
Four extra list-entry records under app-rack-adv add the Utilisation column to both lists on both record types.

## Behaviour notes
- Tabs can overflow on narrow screens; the UI test scrolls the tab bar before selecting a tab.
- Only equipment-type devices are listed; patch panels and other passive items are not.
- All relationship and list records use insert-or-update, so an upgrade overwrites local edits to them.
- The 500-row cap applies per list, not per record.
