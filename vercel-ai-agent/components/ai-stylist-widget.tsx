'use client';

import React, { useState } from 'react';
import { useChat } from '@ai-sdk/react';

export function ShubhashtuAiStylistWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',
    initialMessages: [
      {
        id: 'welcome',
        role: 'assistant',
        content: `Namaste! 🙏 Welcome to **Shubhashtu Fashion**.\n\nI am your personal AI Stylist & Concierge. Ask me anything about earrings, hand-painted tees, delivery times, or tracking!`
      }
    ]
  });

  return (
    <>
      {/* Floating Sparkle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-5 py-2.5 rounded-full bg-gray-950 text-gold border border-gold shadow-2xl hover:bg-gold hover:text-white transition duration-300 font-bold text-xs uppercase tracking-wider"
      >
        <span>✨</span>
        <span>Ask AI Stylist</span>
      </button>

      {/* Floating Chat Modal */}
      {isOpen && (
        <div className="fixed bottom-20 right-6 z-50 w-[92vw] sm:w-[420px] h-[580px] bg-white rounded-3xl shadow-2xl border border-gold/40 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">
          {/* Header */}
          <div className="bg-gray-950 p-4 border-b border-gold/30 flex items-center justify-between text-white">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-gold/20 border border-gold flex items-center justify-center text-gold text-xs">
                ✨
              </div>
              <div>
                <h3 className="font-serif font-bold text-xs uppercase tracking-wider text-white">Shubhashtu AI Stylist</h3>
                <p className="text-[9px] text-amber-300 tracking-widest uppercase font-semibold">Vercel AI SDK</p>
              </div>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white text-sm">
              ✕
            </button>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3.5 text-xs bg-[#fdfafb]">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex items-start gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.role !== 'user' && (
                  <div className="w-6 h-6 rounded-full bg-amber-100 border border-gold text-gold text-[10px] flex items-center justify-center flex-shrink-0">
                    💎
                  </div>
                )}
                <div
                  className={`p-3 rounded-2xl max-w-[85%] text-xs leading-relaxed whitespace-pre-wrap ${
                    m.role === 'user'
                      ? 'bg-gray-900 text-white rounded-tr-none'
                      : 'bg-white text-gray-800 border border-rose-100 rounded-tl-none shadow-sm'
                  }`}
                >
                  {m.content}

                  {/* Render Tool Invocations / Recommendations */}
                  {m.toolInvocations?.map((toolInvocation) => {
                    const toolCallId = toolInvocation.toolCallId;
                    if ('result' in toolInvocation) {
                      const { result } = toolInvocation;
                      if (toolInvocation.toolName === 'searchProducts' && result.products) {
                        return (
                          <div key={toolCallId} className="mt-2.5 grid grid-cols-1 gap-1.5 pt-2 border-t border-gray-100">
                            {result.products.map((p: any) => (
                              <div key={p.id} className="flex items-center justify-between p-2 rounded-xl bg-gray-50 border border-gray-200">
                                <span className="font-bold text-[11px] truncate max-w-[200px]">{p.name}</span>
                                <span className="font-bold text-gold text-xs">₹{p.price}</span>
                              </div>
                            ))}
                          </div>
                        );
                      }
                    }
                    return null;
                  })}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="text-[11px] text-gray-400 italic flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-gold animate-ping"></span>
                <span>AI Stylist is thinking & searching...</span>
              </div>
            )}
          </div>

          {/* Input Footer */}
          <form onSubmit={handleSubmit} className="p-3 bg-white border-t border-rose-100 flex items-center gap-2">
            <input
              value={input}
              onChange={handleInputChange}
              placeholder="Ask about earrings, styling, tees, orders..."
              className="flex-1 px-3.5 py-2 text-xs border border-gray-200 rounded-full focus:outline-none focus:border-gold bg-gray-50"
            />
            <button
              type="submit"
              disabled={isLoading || !input}
              className="w-8 h-8 rounded-full bg-gray-950 text-white hover:bg-gold disabled:opacity-40 transition flex items-center justify-center"
            >
              ➤
            </button>
          </form>
        </div>
      )}
    </>
  );
}

