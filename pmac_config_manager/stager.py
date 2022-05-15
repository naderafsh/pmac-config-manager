from time import sleep, time


class stager:
    times = ...  # type: list
    time_laps = ...  # type: list
    verbose_levels = ...  # type: list
    verbose_level = ...  # type: int
    print_end = ...  # type: str

    print_close = ...  # type: str

    def __init__(self, verbose_level=0, default_end=": ", default_close="*\n"):
        self.times = []
        self.verbose_level = verbose_level
        self.print_end = default_end
        self.verbose_levels = []
        self.print_close = default_close

    def stage(self, fstring=None, this_verbose_level=1, times=None, laps_time=True, print_end=""):

        # new stage

        if not fstring:
            return False

        if laps_time:
            abbr_str = fstring.split()[0]
            self.times.append([abbr_str, time(), this_verbose_level])
            self.verbose_levels.append(this_verbose_level)

            if len(self.times) > 1:

                self.time_laps.append(
                    (self.times[-2][0], round(self.times[-1][1] - self.times[-2][1], 3))
                )

                # close the last stage
                if self.verbose_levels[-2] <= self.verbose_level:
                    print(self.print_close, end="")

            else:
                self.time_laps = []

        if this_verbose_level <= self.verbose_level:
        
            if not print_end:
                print(fstring, end=self.print_end)
            else:
                print(fstring, end=print_end)


        return True


if __name__ == "__main__":
    pass
