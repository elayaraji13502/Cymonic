import os

app_content = """import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
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
"""

css_content = """@import "tailwindcss";

@theme {
  --color-primary: #2563EB;
  --color-success: #16A34A;
  --color-warning: #EAB308;
  --color-danger: #DC2626;
}

:root {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;

  color-scheme: light dark;
  color: rgba(255, 255, 255, 0.87);
  background-color: #f8fafc;

  font-synthesize: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  color: #1e293b;
}
"""

with open(r'c:\Users\Gopi krishna\Cymonic\frontend\src\App.tsx', 'w', encoding='utf-8') as f:
    f.write(app_content)

with open(r'c:\Users\Gopi krishna\Cymonic\frontend\src\index.css', 'w', encoding='utf-8') as f:
    f.write(css_content)
