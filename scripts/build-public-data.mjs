import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const privatePath = fileURLToPath(new URL("../output/residents.json", import.meta.url));
const publicPath = fileURLToPath(new URL("../output/residents.public.json", import.meta.url));
const data = JSON.parse(await readFile(privatePath, "utf8"));

// Fields that must never be published.
const PRIVATE_FIELDS = ["pn", "cadastral", "mortgage", "doc", "docNo", "date"];

// Helper function to mask ALL names to initials: 
function maskName(name) {
  if (!name) return name;
  
  // Handle multiple owners separated by commas
  return name.split(',').map(part => {
    const words = part.trim().split(' ').filter(w => w.length > 0);
    // Map every word (first, last, middle) to its initial + "."
    return words.map(w => `${w[0]}.`).join(' ');
  }).join(', ');
}

for (const record of [...data.units, ...data.non_residential]) {
  for (const field of PRIVATE_FIELDS) delete record[field];
  
  // Apply the masking to the owner's name
  if (record.owner) {
    record.owner = maskName(record.owner);
  }
}
delete data.cadastral;

await writeFile(publicPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
console.log("✅ Created output/residents.public.json. PII removed and names fully masked to initials.");