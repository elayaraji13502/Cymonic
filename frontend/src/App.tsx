import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import Login from './pages/auth/Login';
import StudentLayout from './components/layout/student/StudentLayout';
import MentorLayout from './components/layout/mentor/MentorLayout';
import StudentDashboard from './pages/student/Dashboard';
import AICoach from './pages/student/AICoach';
import MentorDashboard from './pages/mentor/Dashboard';
import StudentProfile from './pages/mentor/StudentProfile';
import NotFound from './pages/NotFound';

// Placeholder components for incomplete routes
const Placeholder = ({ title }: { title: string }) => (
  <div className="p-8"><h1 className="text-2xl font-bold">{title}</h1><p className="text-gray-500">Coming soon...</p></div>
);

function App() {
  return (
    <Router>
      <Toaster position="top-right" richColors />
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />
        
        {/* Student Portal */}
        <Route path="/student" element={<StudentLayout />}>
          <Route path="dashboard" element={<StudentDashboard />} />
          <Route path="coach" element={<AICoach />} />
          <Route path="courses" element={<Placeholder title="My Courses" />} />
          <Route path="progress" element={<Placeholder title="My Progress" />} />
          <Route path="certification" element={<Placeholder title="Certification" />} />
          <Route path="history" element={<Placeholder title="Decision History" />} />
        </Route>

        {/* Mentor Portal */}
        <Route path="/mentor" element={<MentorLayout />}>
          <Route path="dashboard" element={<MentorDashboard />} />
          <Route path="students/:studentId" element={<StudentProfile />} />
          <Route path="students" element={<Placeholder title="All Students" />} />
          <Route path="at-risk" element={<Placeholder title="At-Risk Students" />} />
          <Route path="mentorship" element={<Placeholder title="Mentorship Queue" />} />
          <Route path="courses" element={<Placeholder title="Course Management" />} />
          <Route path="analytics" element={<Placeholder title="Analytics" />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Router>
  );
}

export default App;
