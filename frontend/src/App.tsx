import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Learners from './pages/Learners';
import Performance from './pages/Performance';
import Reasoning from './pages/Reasoning';
import LearningPath from './pages/LearningPath';
import Mentor from './pages/Mentor';
import Certification from './pages/Certification';
import History from './pages/History';
import NotFound from './pages/NotFound';

function App() {
  return (
    <Router>
      <Toaster position="top-right" richColors />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="learners" element={<Learners />} />
          <Route path="performance/:learnerId/:lessonId" element={<Performance />} />
          <Route path="reasoning/:learnerId/:lessonId" element={<Reasoning />} />
          <Route path="learning-path/:learnerId" element={<LearningPath />} />
          <Route path="mentor" element={<Mentor />} />
          <Route path="certification/:learnerId/:courseId" element={<Certification />} />
          <Route path="history/:learnerId" element={<History />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
