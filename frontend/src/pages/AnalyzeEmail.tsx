import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../services/api";
import { AlertCircle, CheckCircle2, Shield, UploadCloud, Edit3, Image as ImageIcon } from "lucide-react";
import clsx from "clsx";

export function AnalyzeEmail() {
  const [activeTab, setActiveTab] = useState<"text" | "screenshot">("text");
  
  // Text Tab State
  const [textInput, setTextInput] = useState("");
  
  // Screenshot Tab State
  const [file, setFile] = useState<File | null>(null);
  const [ocrText, setOcrText] = useState("");
  
  // Result State
  const [result, setResult] = useState<any>(null);

  const analyzeMutation = useMutation({
    mutationFn: (body: string) => api.analyzeManual("Manual Analysis", body),
    onSuccess: (data) => {
      setResult(data);
    },
  });

  const ocrMutation = useMutation({
    mutationFn: (f: File) => api.analyzeOCR(f),
    onSuccess: (data) => {
      setOcrText(data.text);
    },
  });

  const handlePredict = (text: string) => {
    if (!text.trim()) return;
    analyzeMutation.mutate(text);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleOcr = () => {
    if (!file) return;
    ocrMutation.mutate(file);
  };

  const reset = () => {
    setResult(null);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Manual Email Analysis</h1>
        <p className="text-slate-500 mt-1">
          Analyze suspicious content by pasting text or uploading a screenshot.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => { setActiveTab("text"); reset(); }}
            className={clsx(
              "flex-1 py-4 text-sm font-medium transition-colors",
              activeTab === "text" ? "text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50" : "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
            )}
          >
            <div className="flex items-center justify-center gap-2">
              <Edit3 size={18} />
              Paste Text
            </div>
          </button>
          <button
            onClick={() => { setActiveTab("screenshot"); reset(); }}
            className={clsx(
              "flex-1 py-4 text-sm font-medium transition-colors",
              activeTab === "screenshot" ? "text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/50" : "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
            )}
          >
            <div className="flex items-center justify-center gap-2">
              <ImageIcon size={18} />
              Upload Screenshot
            </div>
          </button>
        </div>

        <div className="p-6">
          {activeTab === "text" && (
            <div className="space-y-4">
              <label className="block text-sm font-medium text-slate-700">
                Email Content
              </label>
              <textarea
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                rows={10}
                className="w-full rounded-lg border-slate-300 border p-4 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm resize-y"
                placeholder="Paste the email content here..."
              />
              <div className="flex justify-end">
                <button
                  onClick={() => handlePredict(textInput)}
                  disabled={!textInput.trim() || analyzeMutation.isPending}
                  className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
                >
                  {analyzeMutation.isPending ? "Analyzing..." : "Analyze Content"}
                </button>
              </div>
            </div>
          )}

          {activeTab === "screenshot" && (
            <div className="space-y-6">
              {!ocrText ? (
                <div className="space-y-4">
                  <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 flex flex-col items-center justify-center bg-slate-50 hover:bg-slate-100 transition-colors">
                    <UploadCloud size={48} className="text-slate-400 mb-4" />
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleFileChange}
                      className="hidden"
                      id="file-upload"
                    />
                    <label
                      htmlFor="file-upload"
                      className="cursor-pointer bg-white border border-slate-300 text-slate-700 px-4 py-2 rounded-lg font-medium hover:bg-slate-50 transition-colors"
                    >
                      Browse Files
                    </label>
                    <p className="text-sm text-slate-500 mt-2">
                      {file ? file.name : "Supported formats: PNG, JPG"}
                    </p>
                  </div>
                  
                  <div className="flex justify-end">
                    <button
                      onClick={handleOcr}
                      disabled={!file || ocrMutation.isPending}
                      className="bg-slate-800 text-white px-6 py-2 rounded-lg font-medium hover:bg-slate-900 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
                    >
                      {ocrMutation.isPending ? "Extracting Text..." : "Extract Text (OCR)"}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4 fade-in">
                  <div className="flex items-center justify-between">
                    <label className="block text-sm font-medium text-slate-700">
                      OCR Extracted Text <span className="text-slate-400 font-normal">(Review and edit before analysis)</span>
                    </label>
                    <button 
                      onClick={() => { setOcrText(""); setFile(null); }}
                      className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      Start Over
                    </button>
                  </div>
                  <textarea
                    value={ocrText}
                    onChange={(e) => setOcrText(e.target.value)}
                    rows={10}
                    className="w-full rounded-lg border-indigo-200 border p-4 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm resize-y bg-indigo-50/30"
                  />
                  <div className="flex justify-end">
                    <button
                      onClick={() => handlePredict(ocrText)}
                      disabled={!ocrText.trim() || analyzeMutation.isPending}
                      className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors shadow-sm"
                    >
                      {analyzeMutation.isPending ? "Analyzing..." : "Analyze Content"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {analyzeMutation.isError && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg flex items-start gap-3 border border-red-200 fade-in">
          <AlertCircle size={20} className="shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium">Analysis Failed</h4>
            <p className="text-sm opacity-90 mt-1">{(analyzeMutation.error as Error).message}</p>
          </div>
        </div>
      )}
      
      {ocrMutation.isError && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg flex items-start gap-3 border border-red-200 fade-in">
          <AlertCircle size={20} className="shrink-0 mt-0.5" />
          <div>
            <h4 className="font-medium">OCR Extraction Failed</h4>
            <p className="text-sm opacity-90 mt-1">{(ocrMutation.error as Error).message}</p>
          </div>
        </div>
      )}

      {result && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm fade-in">
          <div className="p-6">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Shield size={20} className="text-indigo-600" />
              Analysis Result
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-500 font-medium">Classification</p>
                  <p className="text-xl font-bold mt-1">
                    {result.classification === "SPAM" ? (
                      <span className="text-red-600 flex items-center gap-2">
                        <AlertCircle size={20} /> SPAM
                      </span>
                    ) : (
                      <span className="text-green-600 flex items-center gap-2">
                        <CheckCircle2 size={20} /> HAM
                      </span>
                    )}
                  </p>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-100">
                <p className="text-sm text-slate-500 font-medium">Decision Score</p>
                <div className="mt-1 flex items-baseline gap-2">
                  <p className="text-xl font-bold text-slate-900">
                    {result.decision_score.toFixed(4)}
                  </p>
                </div>
              </div>
              
              <div className="p-4 rounded-lg bg-slate-50 border border-slate-100 md:col-span-2">
                <p className="text-sm text-slate-500 font-medium">Model Version</p>
                <p className="text-lg font-medium text-slate-900 mt-1">
                  {result.model_version}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
