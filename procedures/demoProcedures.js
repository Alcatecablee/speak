/*
 * DEVELOPMENT DEMO DATA ONLY.
 * These are invented examples used to prove the contextual-reminder concept inside Speak Your Notes.
 * They are NOT real procedures and are not connected to Procedure Hub or any real organisation.
 *
 * This file is the ONLY place demo procedures live. The UI never imports it – it talks to a
 * procedure service (see procedureService.js), which a real Procedure Hub API client can replace.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.ProcedureHub = root.ProcedureHub || {}).demoProcedures = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const SOURCE = 'Procedure Hub (demo data)';

  return [
    {
      id: 'demo-till-roll-supply',
      title: 'Till Roll Slip Supply',
      status: 'Active',
      version: 1,
      effectiveDate: '2026-10-01',
      lastUpdated: '2026-10-01T09:30:00+02:00',
      instruction: 'Do not supply clients with till roll slips outside Limpopo. Till roll slips may only be supplied to clients in Limpopo.',
      source: SOURCE,
      isDemo: true,
      concepts: [
        { name: 'till roll', terms: ['till roll', 'till roll slip', 'till roll slips', 'supply till roll'], weight: 3, required: true },
        { name: 'supply', terms: ['supply', 'supplied', 'supplying', 'we dont supply'], weight: 2 },
        { name: 'limpopo', terms: ['limpopo'], weight: 2 },
      ],
    },
    {
      id: 'demo-open-tables-cash-up',
      title: 'Open Tables Before Cash-Up',
      status: 'Active',
      version: 1,
      effectiveDate: '2026-10-03',
      lastUpdated: '2026-10-03T08:00:00+02:00',
      instruction: 'Ensure all open tables are closed before completing the cash-up.',
      source: SOURCE,
      isDemo: true,
      concepts: [
        { name: 'cash up', terms: ['cash up', 'cashup', 'cashing up', 'cashed up'], weight: 3, required: true },
        { name: 'open tables', terms: ['open table', 'table open', 'table still open', 'unclosed table', 'tables open'], weight: 2 },
        { name: 'problem', terms: ['cannot', 'cant', 'unable', 'not able', 'wont', 'failed', 'error', 'stuck'], weight: 1 },
      ],
    },
    {
      id: 'demo-kitchen-printer-offline',
      title: 'Kitchen Printer Offline',
      status: 'Active',
      version: 2,
      effectiveDate: '2026-09-24',
      lastUpdated: '2026-09-24T14:15:00+02:00',
      instruction: 'Check the printer power and network connection before escalating the issue.',
      source: SOURCE,
      isDemo: true,
      concepts: [
        { name: 'kitchen printer', terms: ['kitchen printer'], weight: 3 },
        { name: 'kitchen', terms: ['kitchen'], weight: 2 },
        { name: 'printer', terms: ['printer'], weight: 1 },
        { name: 'printer problem', terms: ['offline', 'printer offline', 'not printing', 'stopped printing', 'stop printing', 'not responding'], weight: 2 },
      ],
    },
    {
      id: 'demo-adumo-ped-troubleshooting',
      title: 'Adumo PED Troubleshooting',
      status: 'Active',
      version: 3,
      effectiveDate: '2026-09-15',
      lastUpdated: '2026-09-29T11:00:00+02:00',
      instruction: 'Follow the approved troubleshooting steps for the Adumo PED before escalating the issue.',
      source: SOURCE,
      isDemo: true,
      concepts: [
        { name: 'adumo', terms: ['adumo'], weight: 2 },
        { name: 'device', terms: ['ped', 'card machine', 'payment terminal'], weight: 3 },
        { name: 'terminal', terms: ['terminal'], weight: 1 },
        { name: 'problem', terms: ['offline', 'not connecting', 'not working', 'not communicating', 'wont connect'], weight: 2 },
      ],
    },
  ];
});
