import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { TrendingUp, Clock, Target, Zap } from 'lucide-react';

const StudentProgress = () => {
  const scoreData = [
    { name: 'Mod 1', score: 85 },
    { name: 'Mod 2', score: 78 },
    { name: 'Mod 3', score: 62 },
    { name: 'Mod 4', score: 58 },
    { name: 'Mod 5', score: 65 },
  ];

  const attemptData = [
    { name: 'Mod 1', attempts: 1 },
    { name: 'Mod 2', attempts: 1 },
    { name: 'Mod 3', attempts: 3 },
    { name: 'Mod 4', attempts: 4 },
    { name: 'Mod 5', attempts: 2 },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">My Progress</h1>
        <p className="text-gray-500 mt-1">Detailed analytics of your learning journey.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp className="w-5 h-5 text-blue-500" />
            <h3 className="font-semibold text-gray-700">Average Score</h3>
          </div>
          <p className="text-3xl font-bold text-gray-900">69.6%</p>
          <p className="text-sm text-red-500 mt-1">↓ 4% from last module</p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <Target className="w-5 h-5 text-green-500" />
            <h3 className="font-semibold text-gray-700">Modules Mastered</h3>
          </div>
          <p className="text-3xl font-bold text-gray-900">2 / 8</p>
          <p className="text-sm text-gray-500 mt-1">Python Fundamentals</p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <Clock className="w-5 h-5 text-purple-500" />
            <h3 className="font-semibold text-gray-700">Time Spent</h3>
          </div>
          <p className="text-3xl font-bold text-gray-900">14h 20m</p>
          <p className="text-sm text-gray-500 mt-1">This week</p>
        </div>
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-5 h-5 text-amber-500" />
            <h3 className="font-semibold text-gray-700">Learning Velocity</h3>
          </div>
          <p className="text-3xl font-bold text-gray-900">Slow</p>
          <p className="text-sm text-amber-600 mt-1">Needs reinforcement</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h3 className="text-lg font-bold text-gray-900 mb-6">Assessment Scores</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={scoreData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} />
                <YAxis axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip />
                <Line type="monotone" dataKey="score" stroke="#2563EB" strokeWidth={3} dot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h3 className="text-lg font-bold text-gray-900 mb-6">Attempts per Module</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={attemptData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} />
                <YAxis axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="attempts" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentProgress;
