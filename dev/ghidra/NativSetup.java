// Marks a game module's functions from dev/ghidra/make_elf.py's list (ARM or Thumb, named), for analyzeHeadless as a
// preScript: <program file>.functions beside the imported ELF. Arguments: the list's path.
//@category Nativ
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.io.BufferedReader;
import java.io.FileReader;
import java.math.BigInteger;

public class NativSetup extends GhidraScript {
	@Override
	public void run() throws Exception {
		String list = getScriptArgs()[0];
		Register tmode = currentProgram.getRegister("TMode");
		int n = 0;
		try (BufferedReader r = new BufferedReader(new FileReader(list))) {
			for (String line; (line = r.readLine()) != null;) {
				String[] f = line.trim().split(" ");
				if (f.length < 3) continue;
				Address a = toAddr(Long.parseLong(f[0], 16));
				BigInteger mode = f[1].equals("thumb") ? BigInteger.ONE : BigInteger.ZERO;
				try { currentProgram.getProgramContext().setValue(tmode, a, a, mode); }
				catch (ghidra.program.model.listing.ContextChangeException e) { }   // (already disassembled by the import: keep it)
				disassemble(a);
				Function fn = getFunctionAt(a);
				if (fn == null) fn = createFunction(a, f[2]);
				else fn.setName(f[2], SourceType.IMPORTED);
				if (fn != null) n++;
				if (monitor.isCancelled()) break;
			}
		}
		println("NativSetup: " + n + " functions marked");
	}
}
