import { Slider as SliderPrimitive } from "@base-ui/react/slider"

import { cn } from "@/lib/utils"

type SliderProps = Omit<SliderPrimitive.Root.Props, "value" | "defaultValue" | "onValueChange"> & {
  value?: number | number[]
  defaultValue?: number | number[]
  onValueChange?: (value: number[]) => void
}

function Slider({
  className,
  defaultValue,
  value,
  min = 0,
  max = 100,
  onValueChange,
  ...props
}: SliderProps) {
  // Unwrap single-element arrays — Base UI expects `number` for single-thumb sliders
  const normalizedValue = Array.isArray(value)
    ? value.length === 1 ? value[0] : value
    : value
  const normalizedDefault = Array.isArray(defaultValue)
    ? defaultValue.length === 1 ? defaultValue[0] : defaultValue
    : defaultValue

  const thumbCount = Array.isArray(value) ? value.length
    : Array.isArray(defaultValue) ? defaultValue.length
    : 1

  // Base UI fires number for single-thumb; callers expect number[]
  const handleValueChange = onValueChange
    ? (val: number | number[]) => onValueChange(Array.isArray(val) ? val : [val])
    : undefined

  return (
    <SliderPrimitive.Root
      className={cn("data-horizontal:w-full data-vertical:h-full", className)}
      data-slot="slider"
      defaultValue={normalizedDefault}
      value={normalizedValue}
      min={min}
      max={max}
      thumbAlignment="edge"
      onValueChange={handleValueChange}
      {...props}
    >
      <SliderPrimitive.Control className="relative flex w-full touch-none items-center select-none data-disabled:opacity-50 data-vertical:h-full data-vertical:min-h-40 data-vertical:w-auto data-vertical:flex-col">
        <SliderPrimitive.Track
          data-slot="slider-track"
          className="relative grow overflow-hidden rounded-full bg-muted select-none data-horizontal:h-1 data-horizontal:w-full data-vertical:h-full data-vertical:w-1"
        >
          <SliderPrimitive.Indicator
            data-slot="slider-range"
            className="bg-primary select-none data-horizontal:h-full data-vertical:w-full"
          />
        </SliderPrimitive.Track>
        {Array.from({ length: thumbCount }, (_, index) => (
          <SliderPrimitive.Thumb
            data-slot="slider-thumb"
            key={index}
            className="relative block size-3 shrink-0 rounded-full border border-ring bg-white ring-ring/50 transition-[color,box-shadow] select-none after:absolute after:-inset-2 hover:ring-3 focus-visible:ring-3 focus-visible:outline-hidden active:ring-3 disabled:pointer-events-none disabled:opacity-50"
          />
        ))}
      </SliderPrimitive.Control>
    </SliderPrimitive.Root>
  )
}

export { Slider }
