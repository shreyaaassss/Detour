import { Navigate, Route, Routes } from 'react-router-dom'
import Dispatch from './pages/Dispatch'
import Driver from './pages/Driver'
import Head from './pages/Head'
import Landing from './site/Landing'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/dispatch" element={<Dispatch />} />
      <Route path="/driver" element={<Driver />} />
      <Route path="/head" element={<Head />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
