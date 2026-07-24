import type { InputHTMLAttributes, Ref } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  ref?: Ref<HTMLInputElement>;
}

export const Input = ({ label, id, error, ref, className, ...props }: InputProps) => {
  const inputId = id ?? props.name;

  return (
    <div>
      <label htmlFor={inputId} className="mb-1 block text-sm font-bold text-gray-700">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        className={["input", error ? "focus:border-red-400 focus:ring-red-100" : "", className]
          .filter(Boolean)
          .join(" ")}
        {...props}
      />
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
    </div>
  );
};
