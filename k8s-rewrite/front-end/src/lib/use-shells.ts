"use client";

import { useState, useEffect } from "react";
import { getShells, getMaximized, subscribe, ShellInstance } from "./shell-manager";

/**
 * React hook — subscribes to the shell manager and returns
 * the current shells array + maximized shell.
 */
export function useShells() {
  const [shells, setShells] = useState<ShellInstance[]>(getShells);
  const [maximized, setMaximized] = useState<ShellInstance | null>(getMaximized);

  useEffect(() => {
    return subscribe(() => {
      setShells(getShells());
      setMaximized(getMaximized());
    });
  }, []);

  return { shells, maximized };
}
