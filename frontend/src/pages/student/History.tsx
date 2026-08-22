import { BrainCircuit, ArrowRight } from 'lucide-react';

const StudentHistory = () => {
  const history = [
    { id: 1, date: 'Aug 22, 2026', lesson: 'Recursion', decision: 'mentor', reason: 'Repeated failure despite reinforcement.', confidence: 92, source: 'llm' },
    { id: 2, date: 'Aug 20, 2026', lesson: 'Functions', decision: 'advance', reason: 'Mastery achieved with high score.', confidence: 88, source: 'llm' },
    { id: 3, date: 'Aug 18, 2026', lesson: 'Loops', decision: 'reinforce', reason: 'Score below threshold, needs practice.', confidence: 78, source: 'fallback' },
    { id: 4, date: 'Aug 15, 2026', lesson: 'Variables', decision: 'advance', reason: 'Mastery achieved.', confidence: 95, source: 'llm' },
  ];

  const getDecisionColor = (decision: string) => {
    switch (decision) {
      case 'advance': return 'bg-green-100 text-green-800 border-green-200';
      case 'reinforce': return 'bg-amber-100 text-amber-800 border-amber-200';
      case 'mentor': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Decision History</h1>
        <p className="text-gray-500 mt-1">Timeline of AI interventions and recommendations.</p>
      </div>

      <div className="relative border-l-2 border-gray-200 ml-4 space-y-8 pb-8">
        {history.map((item) => (
          <div key={item.id} className="relative pl-8">
            <div className="absolute -left-[9px] top-1 w-4 h-4 rounded-full bg-white border-2 border-blue-500"></div>
            
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                <div>
                  <span className="text-sm text-gray-500 font-medium">{item.date}</span>
                  <h3 className="text-lg font-bold text-gray-900 mt-1">{item.lesson}</h3>
                </div>
                <div className={`px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wider border ${getDecisionColor(item.decision)}`}>
                  {item.decision}
                </div>
              </div>
              
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-100 mb-4">
                <p className="text-gray-700 italic">"{item.reason}"</p>
              </div>
              
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1 text-gray-500">
                    <BrainCircuit className="w-4 h-4" /> {item.source.toUpperCase()}
                  </span>
                  <span className="text-gray-500">
                    Confidence: <strong className="text-gray-900">{item.confidence}%</strong>
                  </span>
                </div>
                <button className="text-blue-600 font-medium hover:underline flex items-center gap-1">
                  View Details <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StudentHistory;
