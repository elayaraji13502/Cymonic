import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter, ArrowRight } from 'lucide-react';
import { mentorService } from '../../services/api';

const MentorStudents = () => {
  const [students, setStudents] = useState<any[]>([]);

  useEffect(() => {
    mentorService.getStudents().then(res => setStudents(res.data));
  }, []);

  const getRecommendationColor = (rec: string) => {
    switch (rec) {
      case 'ADVANCE': return 'bg-green-100 text-green-800';
      case 'REINFORCE': return 'bg-amber-100 text-amber-800';
      case 'MENTOR': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">All Students</h1>
          <p className="text-gray-500 mt-1">Monitor progress and AI recommendations.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              placeholder="Search students..." 
              className="pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button className="p-2 border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">
            <Filter className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100 text-sm text-gray-500 uppercase tracking-wider">
                <th className="p-4 font-semibold">Student</th>
                <th className="p-4 font-semibold">Course</th>
                <th className="p-4 font-semibold">Progress</th>
                <th className="p-4 font-semibold">Avg Score</th>
                <th className="p-4 font-semibold">AI Rec</th>
                <th className="p-4 font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {students.map(student => (
                <tr key={student.id} className="hover:bg-gray-50 transition-colors">
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center font-bold">
                        {student.name.charAt(0)}
                      </div>
                      <span className="font-semibold text-gray-900">{student.name}</span>
                    </div>
                  </td>
                  <td className="p-4 text-gray-600">{student.course}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <div className="w-full max-w-[100px] bg-gray-100 rounded-full h-2">
                        <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${student.progress}%` }}></div>
                      </div>
                      <span className="text-sm text-gray-600">{student.progress}%</span>
                    </div>
                  </td>
                  <td className="p-4 font-medium text-gray-900">{student.avgScore}%</td>
                  <td className="p-4">
                    <span className={`px-2.5 py-1 rounded-md text-xs font-bold tracking-wider ${getRecommendationColor(student.recommendation)}`}>
                      {student.recommendation}
                    </span>
                  </td>
                  <td className="p-4">
                    <Link 
                      to={`/mentor/students/${student.id}`}
                      className="text-blue-600 hover:text-blue-800 font-medium text-sm flex items-center gap-1"
                    >
                      View <ArrowRight className="w-4 h-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default MentorStudents;
