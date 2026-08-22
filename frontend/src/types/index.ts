export type Role = 'student' | 'mentor';

export interface User {
  id: number;
  name: string;
  role: Role;
  email: string;
}

export interface AIDecision {
  decision: 'advance' | 'reinforce' | 'mentor';
  reasoning: string;
  confidence: number;
  signals: string[];
  reasoning_source: 'llm' | 'fallback';
}

export interface LearnerContext {
  latest_score: number;
  average_score: number;
  trend: 'improving' | 'stable' | 'declining' | 'insufficient_data';
  attempts: number;
  engagement: 'high' | 'medium' | 'low';
  mastery: 'mastered' | 'approaching' | 'not_mastered';
  risk_flags: string[];
}

export interface MentorshipRequest {
  id: number;
  studentId: number;
  studentName: string;
  course: string;
  module: string;
  reason: string;
  message: string;
  priority: 'Low' | 'Medium' | 'High' | 'Urgent';
  status: 'Pending' | 'Scheduled' | 'Completed';
  requestDate: string;
  aiConfidence: number;
}

export interface StudentProgress {
  course: string;
  currentModule: string;
  completion: number;
  averageScore: number;
  learningStreak: number;
  context: LearnerContext;
  aiRecommendation: AIDecision | null;
}
