export const globalInitialTickets = [
  {
    id: 'T-101', issue: 'VPN Connection Failed', description: 'User cannot connect to the corporate VPN from home network. Error code 800.',
    category: 'Network', status: 'Open', priority: 'High', date: '2026-02-24', ai_suggestion: 'Restart VPN Service; Check User Certificate Expiry.', resolution: '', author: 'other'
  },
  {
    id: 'T-102', issue: 'Outlook Crashing', description: 'Outlook closes immediately after opening. Safe mode works.',
    category: 'Software', status: 'In Progress', priority: 'Medium', date: '2026-02-23', ai_suggestion: 'Disable recent add-ins; Repair Office 365 Installation.', resolution: 'Repair initiated, waiting for user feedback.', author: 'other'
  },
  {
    id: 'T-089', issue: 'Monitor not turning on', description: 'My secondary Dell monitor is completely black. Power light is off.',
    category: 'Hardware', status: 'In Progress', priority: 'Medium', date: '2026-02-23', ai_suggestion: 'Check power cable and port.', resolution: 'IT dispatched a new power cable.', author: 'me'
  },
  {
    id: 'T-042', issue: 'SAP Access Denied', description: 'Getting authorization error when trying to approve POs.',
    category: 'Access', status: 'Resolved', priority: 'High', date: '2026-02-15', ai_suggestion: 'Update AD permissions.', resolution: 'Permissions updated in Active Directory.', author: 'me'
  }
];

export const COLORS = ['#818cf8', '#34d399', '#fbbf24', '#f87171', '#c084fc'];
