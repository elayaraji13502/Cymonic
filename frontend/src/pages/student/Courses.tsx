import { BookOpen, Clock, Award, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

const StudentCourses = () => {
  const courses = [
    { id: 10, title: 'Python Fundamentals', instructor: 'Dr. Mehta', progress: 65, difficulty: 'Beginner', modules: 8, completed: 5 },
    { id: 20, title: 'Data Structures', instructor: 'Prof. Sarah', progress: 15, difficulty: 'Intermediate', modules: 10, completed: 1 },
    { id: 30, title: 'Machine Learning Basics', instructor: 'Dr. Mehta', progress: 0, difficulty: 'Advanced', modules: 12, completed: 0 },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">My Courses</h1>
        <p className="text-gray-500 mt-1">Continue your learning journey.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {courses.map(course => (
          <div key={course.id} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
            <div className="h-32 bg-gradient-to-br from-blue-500 to-indigo-600 p-6 flex items-end">
              <h3 className="text-xl font-bold text-white">{course.title}</h3>
            </div>
            <div className="p-6 flex-1 flex flex-col">
              <div className="flex items-center justify-between text-sm text-gray-500 mb-4">
                <span className="flex items-center gap-1"><BookOpen className="w-4 h-4" /> {course.modules} Modules</span>
                <span className="flex items-center gap-1"><Award className="w-4 h-4" /> {course.difficulty}</span>
              </div>
              
              <div className="mb-6">
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium text-gray-700">Progress</span>
                  <span className="font-bold text-blue-600">{course.progress}%</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${course.progress}%` }}></div>
                </div>
                <p className="text-xs text-gray-500 mt-2">{course.completed} of {course.modules} modules completed</p>
              </div>

              <div className="mt-auto">
                <Link 
                  to={`/student/learning-path/${course.id}`}
                  className="w-full py-2.5 bg-gray-50 hover:bg-blue-50 text-blue-600 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                >
                  {course.progress > 0 ? 'Continue Learning' : 'Start Course'} <ArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StudentCourses;
