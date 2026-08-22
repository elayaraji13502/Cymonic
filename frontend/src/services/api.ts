import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// Create axios instance
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Mock Data for Demo Mode
const MOCK_LEARNERS = [
  { id: 1, name: 'Arun', course: 'Python Foundations', currentLesson: 'Recursion', completion: 65, averageScore: 68, risk: 'High', recommendation: 'Mentor' },
  { id: 2, name: 'Priya', course: 'Data Science', currentLesson: 'Pandas', completion: 80, averageScore: 92, risk: 'Low', recommendation: 'Advance' },
  { id: 3, name: 'Rahul', course: 'Web Dev', currentLesson: 'React Hooks', completion: 45, averageScore: 72, risk: 'Medium', recommendation: 'Reinforce' },
];

const MOCK_PERFORMANCE = {
  latest_score: 65,
  average_score: 68,
  trend: 'declining',
  attempt_count: 3,
  attempt_pressure: 'high',
  mastery: { status: 'not_mastered', threshold: 75, evidence: 'Scores are consistently below threshold.' },
  engagement: { status: 'low' },
  intervention: { history: 1, effectiveness: 'ineffective' },
  certification: { required: true, risk: 'high' },
  risk_flags: ['low_engagement', 'repeated_failure'],
};

const MOCK_REASONING = {
  decision: 'mentor',
  reasoning: 'The learner has shown repeated failure despite previous reinforcement and engagement is declining. Mentor intervention is required.',
  confidence: 0.85,
  signals: ['repeated_failure', 'low_engagement', 'high_certification_risk'],
  rejected_alternatives: {
    advance: 'Mastery has not been achieved.',
    reinforce: 'Previous reinforcement was ineffective.'
  },
  reasoning_source: 'llm'
};

const MOCK_LEARNING_PATH = {
  current_lesson: 3,
  completed_lessons: [1, 2],
  next_lesson: 4,
  reinforcement_state: 'none',
  mentor_state: 'pending',
  certification_progress: { eligible: false, course_completion: 40 }
};

const MOCK_CERTIFICATION = {
  course_completion: 40,
  required_lessons_completed: 2,
  required_lessons_total: 5,
  required_assessments_passed: 1,
  required_assessments_total: 3,
  certification_eligible: false
};

const MOCK_HISTORY = [
  { id: 1, timestamp: '2026-08-20T10:00:00Z', lesson: 'Intro to Python', decision: 'advance', reasoning: 'Mastery achieved.', confidence: 0.9, reasoning_source: 'llm' },
  { id: 2, timestamp: '2026-08-21T14:30:00Z', lesson: 'Control Flow', decision: 'reinforce', reasoning: 'Needs practice.', confidence: 0.8, reasoning_source: 'fallback' },
];

// Demo Mode Toggle
let isDemoMode = true;

export const toggleDemoMode = () => {
  isDemoMode = !isDemoMode;
  return isDemoMode;
};

export const getIsDemoMode = () => isDemoMode;

// API Services
export const learnerService = {
  getLearners: async () => {
    if (isDemoMode) return { data: MOCK_LEARNERS };
    return api.get('/learners');
  },
  getPerformance: async (learnerId: number, lessonId: number) => {
    if (isDemoMode) return { data: MOCK_PERFORMANCE };
    return api.get(`/performance/${learnerId}/${lessonId}`);
  },
  evaluateDecision: async (learnerId: number, lessonId: number, context: any) => {
    if (isDemoMode) {
      return new Promise(resolve => setTimeout(() => resolve({ data: MOCK_REASONING }), 1500)); // Simulate AI thinking
    }
    return api.post('/decisions/evaluate', { learner_id: learnerId, lesson_id: lessonId, learner_context: context });
  },
  getLearningPath: async (learnerId: number) => {
    if (isDemoMode) return { data: MOCK_LEARNING_PATH };
    return api.get(`/learning-path/${learnerId}`);
  },
  applyDecision: async (payload: any) => {
    if (isDemoMode) {
      return new Promise(resolve => setTimeout(() => resolve({ data: { status: 'success', action: 'mentor_intervention_created' } }), 800));
    }
    return api.post('/learning-path/apply-decision', payload);
  },
  getCertification: async (learnerId: number, courseId: number) => {
    if (isDemoMode) return { data: MOCK_CERTIFICATION };
    return api.get(`/certification/${learnerId}/${courseId}`);
  },
  getHistory: async (learnerId: number) => {
    if (isDemoMode) return { data: MOCK_HISTORY };
    return api.get(`/history/${learnerId}`);
  }
};
