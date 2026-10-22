import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { MotionConfig } from 'framer-motion'
import { api, getToken, setToken } from './lib/api'
import { Layout } from './components/Layout'
import { AlertsPage, ClientsPage, DashboardPage, ForecastPage, ProfitabilityPage, QuotesPage, ReportsPage, SettingsPage, TransactionsPage } from './pages/Pages'
import { Login } from './pages/Login'

export default function App() {
  const [token,setLocalToken] = useState(getToken())
  const queryClient = useQueryClient()
  useEffect(() => {
    const expire = () => { setToken(null); setLocalToken(null); queryClient.clear() }
    window.addEventListener('finpilot:auth-expired',expire)
    return () => window.removeEventListener('finpilot:auth-expired',expire)
  },[queryClient])
  if (!token) return <MotionConfig reducedMotion="user"><Login onLogin={() => { setLocalToken(getToken()); queryClient.clear() }}/></MotionConfig>
  return <MotionConfig reducedMotion="user"><Routes><Route element={<Layout/>}>
    <Route index element={<Navigate to="/dashboard" replace/>}/>
    <Route path="dashboard" element={<DashboardPage/>}/><Route path="transactions" element={<TransactionsPage/>}/><Route path="clients" element={<ClientsPage/>}/><Route path="quotes" element={<QuotesPage/>}/><Route path="profitability" element={<ProfitabilityPage/>}/><Route path="alerts" element={<AlertsPage/>}/><Route path="forecast" element={<ForecastPage/>}/><Route path="reports" element={<ReportsPage/>}/><Route path="settings" element={<SettingsPage/>}/>
    <Route path="*" element={<Navigate to="/dashboard" replace/>}/>
  </Route></Routes></MotionConfig>
}
