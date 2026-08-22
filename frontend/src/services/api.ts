import axios from 'axios';
import type { AIDecision, LearnerContext, MentorshipRequest, StudentProgress, User } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// --- MOCK DATA FOR DEMO MODE ---
const MOCK_USERS: User[] = [
  { id: 1, name: 'Arun', role: 'student', email: 'student@demo.com' },
  { id: 2, name: 'Dr. Mehta', role: 'mentor', email: 'mentor@demo.com' },
];

const MOCK_STUDENT_PROGRESS: Record<number, StudentProgress> = {
  1: {
    course: 'Python Fundamentals',
    currentModule: 'Recursion',
    completion: 65,
    averageScore: 62,
    learningStreak: 3,
    context: {
      latest_score: 58,
      average_score: 62,
      trend: 'declining',
      attempts: 4,
      engagement: 'low',
      mastery: 'not_mastered',
      risk_flags: ['Repeated Failure', 'Low Engagement', 'Reinforcement Ineffective'],
    },
    aiRecommendation: {
      decision: 'mentor',
      reasoning: 'The learner continues to struggle despite previous reinforcement. A mentor intervention is recommended.',
      confidence: 0.92,
      signals: ['Repeated Failure', 'Low Engagement', 'Reinforcement Ineffective'],
      reasoning_source: 'llm',
    }
  }
};

let MOCK_MENTOR_REQUESTS: MentorshipRequest[] = [
  {
    id: 101,
    studentId: 3,
    studentName: 'Priya',
    course: 'Data Science',
    module: 'Pandas',
    reason: 'Concept difficulty',
    message: 'I am having trouble understanding DataFrame merges.',
    priority: 'Medium',
    status: 'Pending',
    requestDate: '2026-08-22T10:00:00Z',
    aiConfidence: 0.85
  }
];

let isDemoMode = import.meta.env.VITE_DEMO_MODE !== 'false';

export const authService = {
  login: async (role: 'student' | 'mentor') => {
    const user = MOCK_USERS.find(u => u.role === role);
    localStorage.setItem('user', JSON.stringify(user));
    return { data: user };
  },
  logout: () => {
    localStorage.removeItem('user');
  },
  getCurrentUser: (): User | null => {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  }
};

export const studentService = {
  getProgress: async (studentId: number) => {
    if (isDemoMode) {
      // Return mock data for any student ID to prevent infinite loading in demo mode
      return { data: MOCK_STUDENT_PROGRESS[studentId] || MOCK_STUDENT_PROGRESS[1] };
    }
    return api.get(`/progress/${studentId}`);
  },
  requestMentorship: async (data: Partial<MentorshipRequest>) => {
    if (isDemoMode) {
      const newReq = { ...data, id: Date.now(), status: 'Pending', requestDate: new Date().toISOString() } as MentorshipRequest;
      MOCK_MENTOR_REQUESTS.push(newReq);
      return { data: newReq };
    }
    return api.post('/mentorship/request', data);
  }
};

export const mentorService = {
  getDashboardStats: async () => {
    if (isDemoMode) {
      return { data: { totalStudents: 120, needsAttention: 18, pendingRequests: MOCK_MENTOR_REQUESTS.length, certReady: 24 } };
    }
    return api.get('/mentor/stats');
  },
  getMentorshipRequests: async () => {
    if (isDemoMode) return { data: MOCK_MENTOR_REQUESTS };
    return api.get('/mentor/requests');
  },
  getStudents: async () => {
    if (isDemoMode) {
      return { data: [
        { id: 1, name: 'Arun', course: 'Python', progress: 65, avgScore: 62, engagement: 'Low', recommendation: 'MENTOR', risk: 'High' },
        { id: 2, name: 'Rahul', course: 'Web Dev', progress: 45, avgScore: 72, engagement: 'Medium', recommendation: 'REINFORCE', risk: 'Medium' },
        { id: 4, name: 'Sneha', course: 'Python', progress: 88, avgScore: 91, engagement: 'High', recommendation: 'ADVANCE', risk: 'Low' },
      ]};
    }
    return api.get('/mentor/students');
  }
};
