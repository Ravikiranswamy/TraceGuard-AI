import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getHealth } from '../services/api';

const WorkspaceContext = createContext(null);
export function WorkspaceProvider({ children }) {
  const [mode, setModeState] = useState('demo');
  const [userOverride, setUserOverride] = useState(false);
  const [health, setHealth] = useState({ status: 'checking', model: 'unknown', data: null, message: '' });
  const [session, setSession] = useState([]);
  const [reviewed, setReviewed] = useState([]);

  const setMode = useCallback((newMode) => {
    setUserOverride(true);
    setModeState(newMode);
  }, []);

  const refreshHealth = useCallback(async () => {
    setHealth((s) => ({ ...s, status: 'checking' }));
    try {
      const res = await getHealth();
      setHealth({ status: 'online', model: res?.model_version ? 'detected' : 'unverified', data: res, message: '' });
      if (!userOverride) {
        setModeState('live');
      }
    } catch (e) {
      setHealth({ status: 'offline', model: 'unknown', data: null, message: e.message });
      if (!userOverride) {
        setModeState('demo');
      }
    }
  }, [userOverride]);
  useEffect(() => { refreshHealth(); }, [refreshHealth]);
  const addResult = useCallback((input, result, source) => setSession((prev) => [{
    ...result, sender_account_id: input.sender_account_id,
    receiver_account_id: input.receiver_account_id, amount: input.amount, step: input.step,
    source, recorded_at: new Date().toISOString(),
  }, ...prev]), []);
  const toggleReview = useCallback((id) => setReviewed((r) => r.includes(id) ? r.filter((x) => x !== id) : [...r, id]), []);
  const value = useMemo(() => ({ mode, setMode, health, refreshHealth, session, addResult, reviewed, toggleReview }),
    [mode, setMode, health, refreshHealth, session, addResult, reviewed, toggleReview]);
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}
export const useWorkspace = () => useContext(WorkspaceContext);
