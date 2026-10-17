import { Navigate, Route, Routes } from 'react-router-dom';
import Navigation from './components/Navigation';
import Dashboard from './pages/Dashboard';
import RiskCheck from './pages/RiskCheck';
import TransactionHistory from './pages/TransactionHistory';
import Alerts from './pages/Alerts';
import Networks from './pages/Networks';

export default function App() {
  return <Navigation><Routes>
    <Route path="/" element={<Dashboard/>}/>
    <Route path="/risk-check" element={<RiskCheck/>}/>
    <Route path="/transactions" element={<TransactionHistory/>}/>
    <Route path="/alerts" element={<Alerts/>}/>
    <Route path="/networks" element={<Networks/>}/>
    <Route path="*" element={<Navigate to="/" replace/>}/>
  </Routes></Navigation>;
}
