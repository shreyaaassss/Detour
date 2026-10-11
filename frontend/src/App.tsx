import { Navigate, Route, Routes } from 'react-router-dom'
import DemoLayout from './demo/DemoLayout'
import { ChangesPage, DispatcherPage, DriverPage, HeadPage, PlanPage, RescuePage } from './demo/pages'
import Dispatch from './pages/Dispatch'
import Driver from './pages/Driver'
import Head from './pages/Head'
import About from './site/About'
import Contact from './site/Contact'
import Landing from './site/Landing'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/about" element={<About />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/demo" element={<DemoLayout />}>
        <Route index element={<Navigate to="plan" replace />} />
        <Route path="plan" element={<PlanPage />} />
        <Route path="driver" element={<DriverPage />} />
        <Route path="head" element={<HeadPage />} />
        <Route path="rescue" element={<RescuePage />} />
        <Route path="changes" element={<ChangesPage />} />
        <Route path="dispatcher" element={<DispatcherPage />} />
      </Route>
      <Route path="/dispatch" element={<Dispatch />} />
      <Route path="/driver" element={<Driver />} />
      <Route path="/head" element={<Head />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
