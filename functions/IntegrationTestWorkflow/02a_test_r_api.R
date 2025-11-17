library(arrow)

test_r_api <- function(folder, input4, input2, input3, output1, output2) {
  invocation_id <- faasr_invocation_id()
  msg <- paste0("Using invocation ID: ", invocation_id)
  faasr_log(msg)

  # Test deleting input4
  remote_file <- paste0(invocation_id, "/", input4)
  faasr_delete_file(remote_folder = folder, remote_file = remote_file)
  msg <- paste0("Deleted input4: ", input4)
  faasr_log(msg)

  # Test getting input2
  remote_file <- paste0(invocation_id, "/", input2)
  faasr_get_file(remote_folder = folder, remote_file = remote_file, local_file = input2)
  msg <- paste0("Saved remote file: ", remote_file, " to ", input2)
  faasr_log(msg)

  # Test getting input3 using arrow API
  mys3 <- faasr_arrow_s3_bucket()
  remote_path3 <- mys3$path(file.path(folder, invocation_id, input3))
  arrow_input3 <- arrow::read_csv_arrow(remote_path3)

  # Test putting output1
  cat("Test output1", file = output1, sep = "")
  remote_file <- paste0(invocation_id, "/", output1)
  faasr_put_file(local_file = output1, remote_folder = folder, remote_file = remote_file)
  msg <- paste0("Created output file: ", remote_file, " with content: Test output1")
  faasr_log(msg)

  # Test putting output2
  cat("Test output2", file = output2, sep = "")
  remote_file <- paste0(invocation_id, "/", output2)
  faasr_put_file(local_file = output2, remote_folder = folder, remote_file = remote_file)
  msg <- paste0("Created output file: ", remote_file, " with content: Test output2")
  faasr_log(msg)
}

fail_r <- function() {
  # tryCatch(
  #     {
  #         stop("inside_exception")
  #     },
  #     error = function(e) {
  #         stop("outside_exception")
  #     }
  # )
  stop("outside_exception")
}
