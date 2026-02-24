const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

export async function fetchNlpSuggestions(ticketText, topK = 3, minScore = 0.15) {
  const res = await fetch(`${API_BASE}/api/nlp/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticket_text: ticketText, top_k: topK, min_score: minScore }),
  });
  if (!res.ok) throw new Error('NLP request failed');
  return res.json();
}

export async function sendNlpFeedback(resolutionId, helpful) {
  const res = await fetch(`${API_BASE}/api/nlp/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolution_id: resolutionId, helpful }),
  });
  if (!res.ok) throw new Error('Feedback request failed');
  return res.json();
}
