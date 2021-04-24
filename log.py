import datetime as dt

class logger:
        def __init__ ( self, vLevel):

                self.vLevel = vLevel
                self.lastLineWasNewLine = True

        def log ( self, vLevel, msg):

                if vLevel > self.vLevel:
                        return
                
                today = self.now()
                
                # Prefix without newline
                prefix = today.strftime("%Y-%m-%d %H:%M: ")
                # Prefix with newline
                prefixWithNewline = "\n" + prefix;

                if self.lastLineWasNewLine:
                        print("%s" % (prefix), end='')

                # Replace every newline with newline + prefix, except
                # the last newline (if there is one)
                lastchar = msg[-1];
                msg = msg [ 0:len(msg)-1]
                msgnew = prefixWithNewline.join ( msg.split("\n"));
                
                print("%s%s" % (msgnew, lastchar), end='')
                
                if lastchar == '\n':
                        self.lastLineWasNewLine = True
                else:
                        self.lastLineWasNewLine = False

        def now(self):
                return dt.datetime.today()


if __name__ == "__main__":

        # Test code for logger
        log = logger ( 5)

        log.log ( 1, "123");
        log.log ( 1, "b_l_a_n_k_o  jee\nrivinvaiht\n");
        log.log ( 1, "skäpädäpä\nrivinvaiht\n");
