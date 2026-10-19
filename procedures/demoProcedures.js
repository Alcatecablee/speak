/*
 * DEVELOPMENT DEMO DATA ONLY.
 * Contextual procedures used to demonstrate Procedure Hub surface intelligence in Speak Your Notes.
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
      title: 'IMPORTANT: TILL ROLL SUPPLY RESTRICTION',
      status: 'Active',
      version: 1,
      effectiveDate: '2026-10-01',
      lastUpdated: '2026-10-01T09:30:00+02:00',
      instruction: 'Effective immediately, till roll slips may only be supplied to clients in Polokwane. Do not supply outside Polokwane.',
      source: SOURCE,
      isDemo: true,
      concepts: [
        { name: 'till roll', terms: ['till roll', 'till roll slip', 'till roll slips', 'till rolls'], weight: 3, required: true },
        { name: 'supply', terms: ['supply', 'supplied', 'supplying', "we don't supply", 'dont supply', 'we dont supply', 'cannot supply', 'wont supply', 'restriction'], weight: 2 },
        { name: 'polokwane', terms: ['polokwane', 'outside polokwane', 'in polokwane'], weight: 2 },
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
        { name: 'open tables', terms: ['open table', 'table open', 'table still open', 'unclosed table', 'tables open', 'open tables'], weight: 2 },
        { name: 'problem', terms: ['cannot', "can't", 'cant', 'unable', 'not able', 'won\'t', 'wont', 'failed', 'error', 'stuck', 'issue', 'problem'], weight: 1 },
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
        { name: 'kitchen printer', terms: ['kitchen printer', 'orders printer', 'order printer', 'kitchen printers'], weight: 3 },
        { name: 'kitchen', terms: ['kitchen'], weight: 2 },
        { name: 'printer', terms: ['printer'], weight: 1 },
        { name: 'printer problem', terms: ['offline', 'printer offline', 'not printing', 'stopped printing', 'stop printing', 'not responding', 'down', 'disconnected', 'error', 'issue'], weight: 2 },
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
        { name: 'adumo', terms: ['adumo'], weight: 2, required: true },
        { name: 'device', terms: ['ped', 'card machine', 'payment terminal', 'terminal', 'device', 'pin pad'], weight: 3 },
        { name: 'problem', terms: ['offline', 'not connecting', 'not working', 'not communicating', "won't connect", 'wont connect', 'issue', 'down', 'error'], weight: 2 },
      ],
    },
  ];
});
