---
name: Lumina Lexicon
colors:
  surface: '#f9f9ff'
  surface-dim: '#cfdaf2'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eeff'
  surface-container-high: '#dee8ff'
  surface-container-highest: '#d8e3fb'
  on-surface: '#111c2d'
  on-surface-variant: '#404752'
  inverse-surface: '#263143'
  inverse-on-surface: '#ecf1ff'
  outline: '#707883'
  outline-variant: '#bfc7d4'
  surface-tint: '#0061a4'
  primary: '#0061a4'
  on-primary: '#ffffff'
  primary-container: '#2196f3'
  on-primary-container: '#002c4f'
  inverse-primary: '#9ecaff'
  secondary: '#526069'
  on-secondary: '#ffffff'
  secondary-container: '#d3e2ed'
  on-secondary-container: '#56656e'
  tertiary: '#904d00'
  on-tertiary: '#ffffff'
  tertiary-container: '#db7900'
  on-tertiary-container: '#452200'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d1e4ff'
  primary-fixed-dim: '#9ecaff'
  on-primary-fixed: '#001d36'
  on-primary-fixed-variant: '#00497d'
  secondary-fixed: '#d6e5ef'
  secondary-fixed-dim: '#bac9d3'
  on-secondary-fixed: '#0f1d25'
  on-secondary-fixed-variant: '#3b4951'
  tertiary-fixed: '#ffdcc2'
  tertiary-fixed-dim: '#ffb77b'
  on-tertiary-fixed: '#2e1500'
  on-tertiary-fixed-variant: '#6d3900'
  background: '#f9f9ff'
  on-background: '#111c2d'
  surface-variant: '#d8e3fb'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  container-padding: 24px
  gutter: 16px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style

This design system is built for a multilingual localization environment where clarity, accessibility, and rhythmic flow are paramount. The aesthetic follows a **Corporate / Modern** approach with heavy leanings toward **Minimalism**, ensuring that complex linguistic data remains digestible.

The brand personality is airy and welcoming, designed to reduce the cognitive load of translation tasks. It evokes a sense of professional reliability through systematic alignment and a focused color palette, while maintaining a friendly disposition through soft geometry and generous whitespace. The UI should feel like a premium utility—unobtrusive yet high-performing.

## Colors

The palette is strictly monochromatic in its hue selection, utilizing varying luminances of blue to denote hierarchy and interaction.

- **Primary Blue (#2196F3):** Used for primary actions, active states, and critical path highlights.
- **Light Blue Fill (#E3F2FD):** Applied to secondary buttons, selected list items, and subtle alerts.
- **Surface Grey (#F8FAFC):** Reserved for background grouping, sidebar containers, and "off-white" canvas areas to provide subtle contrast against the pure white cards.
- **Text Neutral (#1E293B):** The primary ink color, providing high legibility without the harshness of pure black.

Avoid the use of dark panels or high-contrast black backgrounds; the interface should always remain high-key and luminous.

## Typography

This design system utilizes **Inter** across all levels to maintain a systematic, utilitarian feel that excels in localized contexts (where character widths vary significantly). 

- **Headlines:** Use tighter letter-spacing and heavier weights to anchor the page. 
- **Body Text:** Standard weight for maximum readability in translation blocks. 
- **Labels:** Used for UI metadata, tags, and small descriptors; these often use medium or semi-bold weights to ensure they don't disappear against the airy background.
- **Localization Note:** Ensure line heights are generous (1.5x for body) to accommodate scripts with descenders or diacritics.

## Layout & Spacing

The layout philosophy relies on a **Fluid Grid** with fixed maximum widths for content readability. A 12-column system is used for desktop (1440px), transitioning to 8 columns for tablet and 4 columns for mobile.

- **Desktop:** 24px margins, 16px gutters.
- **Mobile:** 16px margins, 12px gutters.
- **Rhythm:** All vertical and horizontal spacing must be multiples of 4px. Use "Stack-MD" (16px) as the default gap between related elements within a card and "Stack-LG" (32px) to separate major sections of the interface.

## Elevation & Depth

To maintain the "airy" quality, depth is created through **Tonal Layers** supplemented by **Ambient Shadows**. 

1. **Floor:** Pure White (#FFFFFF) or Surface Grey (#F8FAFC).
2. **Elevated Cards:** Pure White (#FFFFFF) with a soft, diffused shadow: `0px 4px 12px rgba(30, 41, 59, 0.05)`.
3. **Interactive Hover:** Shadows should expand slightly and decrease in opacity to simulate a physical lift: `0px 8px 24px rgba(30, 41, 59, 0.08)`.

Avoid heavy borders; use subtle 1px strokes in Light Blue or Light Grey only when necessary to define boundaries on identical background tones.

## Shapes

The shape language is consistently rounded to project friendliness. A base radius of **12px** (rounded-lg) is the standard for all primary UI containers including buttons, input fields, and cards.

- **Standard Buttons/Inputs:** 12px (rounded-lg).
- **Small Components (Chips/Badges):** 8px (rounded).
- **Large Sections:** 24px (rounded-xl) for distinctive grouping containers.

## Components

### Buttons
- **Primary:** Solid #2196F3 with white text. 12px rounded corners.
- **Secondary:** #E3F2FD background with #2196F3 text. No border.
- **Ghost:** Transparent background with #2196F3 text. Only use for tertiary actions.

### Cards & Containers
- Cards must use a white background with 12px rounded corners and the "Ambient Shadow" defined in the Elevation section. Padding within cards should be a minimum of 24px.

### Input Fields
- Background: #F8FAFC. Border: 1px solid #E3F2FD. On focus, the border transitions to #2196F3 with a subtle blue outer glow. 12px rounded corners.

### Chips & Tags
- Used for language selection or status. Background #E3F2FD with #2196F3 text. Use 8px rounded corners and `label-sm` typography.

### Lists
- Interactive list items should have a hover state of #F8FAFC and an active/selected state of #E3F2FD. Use a vertical 4px blue indicator on the left for active list selection.

### Audio Player / Waveform
- For the text-to-speech component, use a light blue waveform representation. The progress bar should be #2196F3, while the remaining track is #E3F2FD.