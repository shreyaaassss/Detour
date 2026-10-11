import { Navigate, Route, Routes } from 'react-router-dom'
import Dispatch from './pages/Dispatch'
import Driver from './pages/Driver'
import Head from './pages/Head'
import Showcase from './pages/Showcase'
import Landing from './site/Landing'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/demo" element={<Showcase />} />
      <Route path="/dispatch" element={<Dispatch />} />
      <Route path="/driver" element={<Driver />} />
      <Route path="/head" element={<Head />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
