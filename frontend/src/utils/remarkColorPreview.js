import { visit } from 'unist-util-visit';

/**
 * Remarks plugin to detect hex color codes and wrap them in a custom link.
 * Transforms: "#e377c2" -> "[#e377c2](#color-preview)" or similar structure
 * so that a custom renderer can pick it up.
 */
export default function remarkColorPreview() {
  return (tree) => {
    visit(tree, 'text', (node, index, parent) => {
      // Regex for hex color codes: # followed by 3, 4, 6, or 8 hex digits
      // We'll stick to 6 or 3 for simplicity as per common use, or 6/8.
      // Boundaries are important to avoid matching inside words.
      const colorRegex = /#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g;
      
      if (!node.value || !colorRegex.test(node.value)) {
        return;
      }

      const value = node.value;
      const children = [];
      let lastIndex = 0;
      let match;

      colorRegex.lastIndex = 0; // Reset regex

      while ((match = colorRegex.exec(value)) !== null) {
        const start = match.index;
        const end = match.index + match[0].length;
        const color = match[0];

        // Add text before the match
        if (start > lastIndex) {
          children.push({
            type: 'text',
            value: value.slice(lastIndex, start),
          });
        }

        // Add the color preview "link"
        // We use a link with a special href that our renderer will recognize
        children.push({
          type: 'link',
          title: null,
          url: '#color-preview', // Marker for our custom renderer
          children: [
            {
              type: 'text',
              value: color,
            },
          ],
          data: {
             hProperties: {
                 'data-color': color // Pass color as data attribute for easier access if needed
             }
          }
        });

        lastIndex = end;
      }

      // Add remaining text
      if (lastIndex < value.length) {
        children.push({
          type: 'text',
          value: value.slice(lastIndex),
        });
      }

      // Replace the current text node with the new children
      parent.children.splice(index, 1, ...children);
      
      // Since we modified the array while iterating, we might need to skip the new nodes?
      // unist-util-visit handles array modification if we return the new index?
      // Actually, 'visit' documentation says:
      // "When a node is replaced, the visitor is called for the replacement."
      // But we replaced one text node with multiple nodes (text, link, text).
      // If we return 'index + children.length', we skip the newly added nodes?
      // For safely, let's return index + children.length to continue after.
      return index + children.length;
    });
  };
}
