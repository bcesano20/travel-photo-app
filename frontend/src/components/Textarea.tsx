import type { TextareaHTMLAttributes } from "react";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  error?: string;
}

export const Textarea = ({ label, id, error, className, ...props }: TextareaProps) => {
  const textareaId = id ?? props.name;

  return (
    <div>
      <label htmlFor={textareaId} className="mb-1 block text-sm font-medium text-gray-700">
        {label}
      </label>
      <textarea
        id={textareaId}
        className={["input", error ? "focus:border-red-400 focus:ring-red-100" : "", className]
          .filter(Boolean)
          .join(" ")}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
    </div>
  );
};
