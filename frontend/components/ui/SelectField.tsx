"use client";

// Shared accessible select for company filters.
import * as SelectPrimitive from "@radix-ui/react-select";

type Option = { value: string; label: string; shortLabel?: string };

type Props = {
  id: string;
  value: string;
  onValueChange: (value: string) => void;
  options: Option[];
};

export default function SelectField({ id, value, onValueChange, options }: Props) {
  const selected = options.find((option) => option.value === value);
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger
        id={id}
        title={selected?.label}
        className="flex h-11 w-full items-center justify-between gap-2 rounded-md border border-neutral-300 bg-white px-3 text-left text-sm text-neutral-900 shadow-sm hover:border-neutral-400 focus:outline-none focus:ring-2 focus:ring-signal/30"
      >
        <span className="min-w-0 flex-1 truncate whitespace-nowrap"><SelectPrimitive.Value>{selected?.shortLabel ?? selected?.label}</SelectPrimitive.Value></span>
        <SelectPrimitive.Icon aria-hidden="true" className="shrink-0 text-neutral-500">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="m4 6 4 4 4-4" />
          </svg>
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content position="popper" sideOffset={4} className="z-50 max-h-72 w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-neutral-200 bg-white p-1 shadow-lg">
          <SelectPrimitive.Viewport>
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                className="relative flex min-h-9 cursor-pointer select-none items-center rounded-sm py-2 pl-3 pr-8 text-sm text-neutral-900 outline-none focus:bg-neutral-100 data-[state=checked]:font-medium"
              >
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="absolute right-3 text-signal" aria-hidden="true">✓</SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
