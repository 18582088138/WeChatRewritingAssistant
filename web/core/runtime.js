// Composition root supplies navigation/render commands; feature modules do not import pages.
export const runtime = {};
export function configureRuntime(commands) {
  Object.assign(runtime, commands);
}
