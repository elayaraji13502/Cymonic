import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import Login from './pages/auth/Login';
import StudentLayout from './components/layout/student/StudentLayout';
import MentorLayout from './components/layout/mentor/MentorLayout';
import StudentDashboard from './pages/student/Dashboard';
import AICoach from './pages/student/AICoach';
import StudentCourses from './pages/student/Courses';
import StudentProgress from './pages/student/Progress';
import StudentCertification from './pages/student/Certification';
import StudentHistory from './pages/student/History';
import MentorDashboard from './pages/mentor/Dashboard';
import StudentProfile from './pages/mentor/StudentProfile';
import MentorStudents from './pages/mentor/Students';
import MentorAtRisk from './pages/mentor/AtRisk';
import MentorQueue from './pages/mentor/MentorshipQueue';
import MentorCourses from './pages/mentor/Courses';
import MentorAnalytics from './pages/mentor/Analytics';
import NotFound from './pages/NotFound';

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
          <Route path="courses" element={<StudentCourses />} />
          <Route path="progress" element={<StudentProgress />} />
          <Route path="certification" element={<StudentCertification />} />
          <Route path="history" element={<StudentHistory />} />
        </Route>

        {/* Mentor Portal */}
        <Route path="/mentor" element={<MentorLayout />}>
          <Route path="dashboard" element={<MentorDashboard />} />
          <Route path="students/:studentId" element={<StudentProfile />} />
          <Route path="students" element={<MentorStudents />} />
          <Route path="at-risk" element={<MentorAtRisk />} />
          <Route path="mentorship" element={<MentorQueue />} />
          <Route path="courses" element={<MentorCourses />} />
          <Route path="analytics" element={<MentorAnalytics />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Router>
  );
}

export default App;
