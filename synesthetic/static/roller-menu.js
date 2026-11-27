/* The Roller's command bar: its 8 blocks and every menu path under them.
   To add an option, add one line to the right list. The page draws the menus from this tree.

   A block or menu item is one of:
     {label, children: [...]}                      a folder: opens the next menu
     {label, type: 'toggle', set: 'italic'}         on / off
     {label, type: 'choice', set: 'weight', options: [['Thin', 300], ...]}
     {label, type: 'color', set: 'color'}           color swatches (your colors, white, gray, dark, custom)
     {label, type: 'font', set: 'font'}             the fonts lit in Settings, Fonts
     {label, type: 'size', set: 'size'}             up / down buttons, or type a number
     {label, type: 'step', set: 'hl.h', ...}        up / down buttons in steps
     {label, type: 'range', set: 'ls', ...}         - / + buttons and a short slider
     {label, type: 'bump', set: 'size', by: 2}      one tap moves it by `by`
     {label, type: 'clear', set: 'underline'}       removes that enhancer
   Numbers: min, max, step, unit. `words: true` hides an item when only one word is selected.
   A block with `quick` acts on one tap instead of opening a menu; `multi: true` is the Multiple block.

   What `set` names (a look on the selected text):
     weight 300-900, italic, underline.w / underline.color, overline.w / overline.color,
     font, color, size (px), caps, hl.color, hl.h (% of the line), hl.w (em on each side),
     ls (letter spacing, em), ws (word spacing, em), lh (line spacing, on the whole paragraph) */
window.ROLLER_MENU = [
  {id: 'amp', label: 'Text Amplifiers', short: 'Amplify', icon: 'B', children: [
    {label: 'Bold', children: [
      {label: 'Thickness', type: 'choice', set: 'weight', options: [['Thin', 300], ['Regular', 400], ['Bold', 700], ['Heavy', 900]]},
    ]},
    {label: 'Italics', type: 'toggle', set: 'italic'},
    {label: 'Underline', children: [
      {label: 'Thickness', type: 'choice', set: 'underline.w', options: [['Thin', 1], ['Regular', 2], ['Bold', 3], ['Heavy', 5]]},
      {label: 'Line Color', type: 'color', set: 'underline.color'},
      {label: 'Remove underline', type: 'clear', set: 'underline'},
    ]},
    {label: 'Overline', children: [
      {label: 'Thickness', type: 'choice', set: 'overline.w', options: [['Thin', 1], ['Regular', 2], ['Bold', 3], ['Heavy', 5]]},
      {label: 'Line Color', type: 'color', set: 'overline.color'},
      {label: 'Remove overline', type: 'clear', set: 'overline'},
    ]},
  ]},
  {id: 'font', label: 'Font', short: 'Font', icon: 'Aa', children: [
    {label: 'Font Type', type: 'font', set: 'font'},
    {label: 'Font Color', type: 'color', set: 'color'},
    {label: 'Font Size', type: 'size', set: 'size', min: 10, max: 64, step: 2, unit: 'px'},
    {label: 'Add Highlight', children: [
      {label: 'Highlight Color', type: 'color', set: 'hl.color'},
    ]},
    {label: 'Caps', type: 'toggle', set: 'caps'},
  ]},
  {id: 'hl', label: 'Highlight', short: 'Highlight', icon: 'hl', children: [
    {label: 'Highlight Color', type: 'color', set: 'hl.color'},
    {label: 'Highlight Size', children: [
      {label: 'Height', type: 'step', set: 'hl.h', min: 20, max: 100, step: 10, unit: '%'},
      {label: 'Width', type: 'step', set: 'hl.w', min: 0, max: 0.6, step: 0.05, unit: 'em'},
    ]},
    {label: 'Remove highlight', type: 'clear', set: 'hl'},
  ]},
  {id: 'space', label: 'Spacing', short: 'Spacing', icon: 'sp', children: [
    {label: 'Letters', type: 'range', set: 'ls', min: -0.05, max: 0.3, step: 0.01, unit: 'em'},
    {label: 'Words', type: 'range', set: 'ws', min: 0, max: 1, step: 0.05, unit: 'em', words: true},
    {label: 'Lines', type: 'range', set: 'lh', min: 1, max: 3, step: 0.1},
  ]},
  {id: 'caps', label: 'Caps', short: 'Caps', icon: 'AB', quick: {type: 'toggle', set: 'caps'}},
  {id: 'up', label: 'Font Increase', short: 'Font +', icon: 'A+', quick: {type: 'bump', set: 'size', by: 2, min: 10, max: 64}},
  {id: 'down', label: 'Font Decrease', short: 'Font −', icon: 'A-', quick: {type: 'bump', set: 'size', by: -2, min: 10, max: 64}},
  {id: 'multi', label: 'Multiple', short: 'Multiple', icon: 'x3', multi: true},
];
