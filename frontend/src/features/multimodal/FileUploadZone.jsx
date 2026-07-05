/**
 * FileUploadZone — drag-and-drop / click-to-browse file upload area.
 *
 * @param {Function} onFileSelected — called with the File object on selection
 * @param {boolean}  disabled       — disables interaction while uploading
 * @param {string[]} accept         — MIME types to accept (default: image/*, pdf, text)
 */
import React, { useRef, useState } from "react";
import { Upload, FileText, Image, File } from "lucide-react";

const DEFAULT_ACCEPT = [
  "image/jpeg","image/png","image/webp","image/gif","image/bmp",
  "application/pdf",
  "text/plain","text/csv",
].join(",");

function FileIcon({ mimeType }) {
  if (!mimeType) return <File className="w-8 h-8 text-slate-400" />;
  if (mimeType.startsWith("image/")) return <Image className="w-8 h-8 text-indigo-400" />;
  if (mimeType === "application/pdf") return <FileText className="w-8 h-8 text-rose-400" />;
  return <FileText className="w-8 h-8 text-slate-400" />;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileUploadZone({ onFileSelected, disabled = false, accept = DEFAULT_ACCEPT }) {
  const [dragOver, setDragOver] = useState(false);
  const [selected, setSelected] = useState(null);
  const inputRef = useRef(null);

  const handleFile = (file) => {
    if (!file) return;
    setSelected(file);
    onFileSelected?.(file);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => { if (!disabled) inputRef.current?.click(); }}
        className={`relative flex flex-col items-center justify-center gap-3 px-6 py-10
          rounded-2xl border-2 border-dashed cursor-pointer transition-all
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
          ${dragOver
            ? "border-indigo-400 bg-indigo-50 scale-[1.01]"
            : "border-slate-200 bg-slate-50 hover:border-indigo-300 hover:bg-indigo-50/50"
          }`}
      >
        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-colors ${
          dragOver ? "bg-indigo-100" : "bg-white border border-slate-200"
        }`}>
          <Upload className={`w-7 h-7 transition-colors ${dragOver ? "text-indigo-500" : "text-slate-400"}`} />
        </div>

        <div className="text-center">
          <p className="font-semibold text-slate-700">
            {dragOver ? "Drop your file here" : "Drag & drop or click to upload"}
          </p>
          <p className="text-sm text-slate-400 mt-1">
            Supports PDF, JPEG, PNG, WebP, plain text · Max 20 MB
          </p>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={onInputChange}
          disabled={disabled}
        />
      </div>

      {/* Selected file preview */}
      {selected && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-slate-200 bg-white">
          <FileIcon mimeType={selected.type} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-700 truncate">{selected.name}</p>
            <p className="text-xs text-slate-400">{selected.type} · {formatBytes(selected.size)}</p>
          </div>
          {!disabled && (
            <button
              onClick={(e) => { e.stopPropagation(); setSelected(null); onFileSelected?.(null); }}
              className="text-slate-300 hover:text-slate-500 text-lg leading-none"
            >×</button>
          )}
        </div>
      )}
    </div>
  );
}
