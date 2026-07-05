/**
 * LanguageSelector — dropdown listing all 11 supported languages.
 *
 * @param {Object}   props
 * @param {string}   props.value    — currently selected ISO 639-1 code
 * @param {Function} props.onChange — callback(code: string)
 * @param {string}   [props.label]  — optional label text
 */
import React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

const LANGUAGES = [
  { code: "en", name: "English",    native: "English" },
  { code: "hi", name: "Hindi",      native: "हिन्दी" },
  { code: "bn", name: "Bengali",    native: "বাংলা" },
  { code: "ta", name: "Tamil",      native: "தமிழ்" },
  { code: "te", name: "Telugu",     native: "తెలుగు" },
  { code: "mr", name: "Marathi",    native: "मराठी" },
  { code: "gu", name: "Gujarati",   native: "ગુજરાતી" },
  { code: "kn", name: "Kannada",    native: "ಕನ್ನಡ" },
  { code: "ml", name: "Malayalam",  native: "മലയാളം" },
  { code: "pa", name: "Punjabi",    native: "ਪੰਜਾਬੀ" },
  { code: "ur", name: "Urdu",       native: "اردو" },
];

export default function LanguageSelector({ value, onChange, label = "Preferred response language" }) {
  return (
    <div className="space-y-1.5">
      {label && (
        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </Label>
      )}
      <Select value={value || "en"} onValueChange={onChange}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select language" />
        </SelectTrigger>
        <SelectContent>
          {LANGUAGES.map((lang) => (
            <SelectItem key={lang.code} value={lang.code}>
              <span className="flex items-center gap-2">
                <span>{lang.name}</span>
                <span className="text-slate-400 text-xs">{lang.native}</span>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
