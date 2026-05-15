import { mount } from "cypress/react";
import "../../app/globals.css";

Cypress.Commands.add("mount", mount);

declare global {
  namespace Cypress {
    interface Chainable {
      mount: typeof import("cypress/react").mount;
    }
  }
}
