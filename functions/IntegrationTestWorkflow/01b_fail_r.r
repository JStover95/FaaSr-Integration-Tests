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
