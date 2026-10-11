import { Navigate, Route, Routes } from 'react-router-dom'
import Dispatch from './pages/Dispatch'

export default function App() {
  return (
    <Routes>
      <Route path="/dispatch" element={<Dispatch />} />
      <Route path="*" element={<Navigate to="/dispatch" replace />} />
    </Routes>
  )
}
