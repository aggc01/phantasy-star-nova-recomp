// Decompiles the functions named on the command line to C, one file each, for analyzeHeadless as a postScript.
// Arguments: the output folder, then hex addresses (fn_<addr> names work too).
//@category Nativ
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import java.io.File;
import java.io.PrintWriter;

public class NativDecompile extends GhidraScript {
	@Override
	public void run() throws Exception {
		String[] args = getScriptArgs();
		File dir = new File(args[0]);
		dir.mkdirs();
		DecompInterface di = new DecompInterface();
		di.openProgram(currentProgram);
		for (int i = 1; i < args.length; i++) {
			String hex = args[i].replace("fn_", "").replace("0x", "");
			Function fn = getFunctionAt(toAddr(Long.parseLong(hex, 16) & ~1L));
			if (fn == null) { println("no function at " + hex); continue; }
			DecompileResults res = di.decompileFunction(fn, 120, monitor);
			String c = res.decompileCompleted() ? res.getDecompiledFunction().getC() : "/* failed: " + res.getErrorMessage() + " */";
			try (PrintWriter w = new PrintWriter(new File(dir, "fn_" + hex + ".c"))) { w.print(c); }
			println("decompiled fn_" + hex);
		}
		di.dispose();
	}
}
