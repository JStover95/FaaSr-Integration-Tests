r_secret <- function(folder_name) {
    value <- faasr_secret("TEST_SECRET")

    cat(value, file = "secret.txt", sep = "")

    invocation_id <- faasr_invocation_id()

    remote_file <- paste0(invocation_id, "/secret.txt")
    faasr_put_file(
        local_file = "secret.txt",
        remote_file = remote_file,
        remote_folder = folder_name
    )
}
