#!/usr/bin/env Rscript
# GLM-AED-ABM Tutorial as a FaaSr workflow function.
#
# This script defines run_glm_tutorial(folder) for use by the FaaSr Executor.
# When the workflow invokes this action, the Executor calls this function with
# Arguments from the workflow JSON (e.g. folder = "glm-tutorial-runs").
#
# The function:
#   1. Sets the working directory to the tutorial path (baked into the Docker image).
#   2. Sets options(repos) for non-interactive CRAN access.
#   3. Runs the full GLM-AED-ABM tutorial (source GLM-AED-ABM-tutorial.R).
#   4. Uploads the debug log and plot outputs to the workflow data store.
#
# Use this with a workflow JSON that has one action, e.g.:
#   "run-glm-tutorial": {
#     "Arguments": { "folder": "glm-tutorial-runs" },
#     "InvokeNext": [],
#     "FaaSServer": "GH",
#     "Type": "R",
#     "FunctionName": "run_glm_tutorial"
#   }
# and ActionContainers pointing to your GLM-AED-ABM tutorial image, and
# FunctionGitRepo pointing to the repo path that contains this file (e.g.
# "owner/GLM-AED-ABM/faasr").

run_glm_tutorial <- function(folder) {
  tutorial_dir <- "/app/GLM-AED-ABM-tutorial"
  log_file <- file.path(tutorial_dir, "runtime_debug.log")

  invocation_id <- faasr_invocation_id()
  faasr_log(paste0("run_glm_tutorial: invocation ID ", invocation_id))
  faasr_log(paste0("run_glm_tutorial: folder=", folder, ", tutorial_dir=", tutorial_dir))

  # CRAN mirror for non-interactive install.packages in the tutorial
  options(repos = c(CRAN = "https://cloud.r-project.org"))

  # Run tutorial in its directory so paths in the script resolve
  owd <- setwd(tutorial_dir)
  on.exit(setwd(owd), add = TRUE)

  # Optional: write a minimal debug log header before sourcing (tutorial may append)
  cat("GLM-AED-ABM Tutorial - FaaSr workflow run\n", file = log_file)
  cat(format(Sys.time(), "%Y-%m-%d %H:%M:%S %Z"), "\n", file = log_file, append = TRUE)

  # Source the full tutorial (same approach as run_tutorial_with_debug.R)
  exit_code <- 0
  tryCatch(
    source("GLM-AED-ABM-tutorial.R", echo = FALSE, local = new.env()),
    error = function(e) {
      message("Tutorial error: ", conditionMessage(e))
      exit_code <<- 1
    }
  )

  faasr_log(paste0("Tutorial finished with exit_code=", exit_code))

  # Upload debug log and plots to the workflow data store
  prefix <- paste0(invocation_id, "/")

  # Helper function to safely upload files
  safe_upload <- function(local_path, remote_name, description) {
    # Normalize path to ensure it's absolute and properly formatted
    local_path <- normalizePath(local_path, mustWork = FALSE)
    if (!file.exists(local_path)) {
      faasr_log(paste0("Warning: ", description, " not found: ", local_path))
      return(FALSE)
    }
    tryCatch({
      remote_file <- paste0(prefix, remote_name)
      faasr_put_file(local_file = local_path, remote_folder = folder, remote_file = remote_file)
      faasr_log(paste0("Uploaded ", description, ": ", remote_file))
      return(TRUE)
    }, error = function(e) {
      faasr_log(paste0("Error uploading ", description, ": ", conditionMessage(e)))
      return(FALSE)
    })
  }

  # Upload debug log
  safe_upload(log_file, "runtime_debug.log", "debug log")

  # Upload plots
  plots_dir <- file.path(tutorial_dir, "plots")
  plot_names <- c("bioshade_feedback.png", "nutrient_drawdown.png", "stokes_law.png")
  for (p in plot_names) {
    local_path <- file.path(plots_dir, p)
    safe_upload(local_path, p, paste0("plot ", p))
  }

  # Optional: write a small success/failure marker for downstream actions
  marker_name <- paste0("glm_tutorial_exit_", exit_code, ".txt")
  marker_path <- file.path(tutorial_dir, marker_name)
  tryCatch({
    # Write marker file and ensure it's flushed
    con <- file(marker_path, "w")
    writeLines(paste0("exit_code=", exit_code), con)
    close(con)
    # Small delay to ensure file is fully written
    Sys.sleep(0.1)
    safe_upload(marker_path, marker_name, "marker file")
  }, error = function(e) {
    faasr_log(paste0("Error creating marker file: ", conditionMessage(e)))
  })

  invisible(exit_code)
}
